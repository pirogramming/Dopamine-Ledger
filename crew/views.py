# crew/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.http import JsonResponse

from .forms import CrewCreateForm, CrewJoinForm, CrewRenameForm
from .models import Crew, CrewMember, CrewGoal, FeedEvent, generate_invite_code

from datetime import timedelta
from django.db.models import Sum
from django.utils import timezone
from ledger.models import EarnRecord

# ── 헬퍼 ──

def _week_range(today=None):
    """이번 주 월~일 범위. weekly_report와 동일 기준."""
    today = today or timezone.localdate()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end


def _format_hm(total_min):
    """분 → 'N시간 N분' / 'N분'. 0이면 '0분'."""
    total_min = int(round(total_min or 0))
    h, m = divmod(total_min, 60)
    if h > 0:
        return f"{h}시간 {m}분"
    return f"{m}분"


def _sorted_members_with_contribution(crew, sort='contribution'):
    """
    멤버 목록에 이번 주 기여도(earn_min 합계)를 붙이고 정렬해서 반환.
    각 멤버에 부착되는 속성:
      - contribution      : 이번 주 earn_min 합 (정수 분)
      - contribution_hm   : 위를 'N시간 N분'으로 포맷한 문자열
      - contribution_pct  : 크루 전체 earn 중 내 비율 (정수 %)
      - feed_text         : 임시 피드 문구 (FeedEvent 붙이면 교체)
    쿼리는 집계 1번.
    """
    members = list(crew.members.select_related('users'))
    week_start, week_end = _week_range()

    member_user_ids = [m.users_id for m in members]
    earn_map = {
        row['users']: int(round(row['total'] or 0))
        for row in EarnRecord.objects
            .filter(users_id__in=member_user_ids,
                    earn_date__range=[week_start, week_end])
            .values('users')
            .annotate(total=Sum('earn_min'))
    }

    total_earn = sum(earn_map.values())   # 크루 전체 이번 주 earn (퍼센트 분모)

    # 멤버별 최신 벌이 피드 (이번 주, earn 타입) 한 방에 조회
    latest_feed = {}
    feed_qs = (
        FeedEvent.objects
        .filter(crew=crew, event_type=FeedEvent.EventType.EARN,
                created_at__date__range=[week_start, week_end])
        .order_by('actor_id', '-created_at')
    )
    for fe in feed_qs:
        if fe.actor_id not in latest_feed:   # actor별 첫 번째 = 최신
            latest_feed[fe.actor_id] = fe.message

    for m in members:
        mins = earn_map.get(m.users_id, 0)
        m.contribution = mins
        m.contribution_hm = _format_hm(mins)
        m.contribution_pct = round(mins / total_earn * 100) if total_earn > 0 else 0
        m.feed_text = latest_feed.get(m.users_id, "이번 주 활동 없음")

    # 정렬
    if sort == 'name':
        members.sort(key=lambda m: str(m.users))
    elif sort == 'joined':
        members.sort(key=lambda m: m.joined_date)
    else:  # 'contribution'
        members.sort(key=lambda m: m.contribution, reverse=True)

    return members

def _goal_progress(crew):
    """
    크루 목표 달성률 계산.
    반환: (모은 분, 목표 분, 퍼센트, 달성여부) 또는 goal 없으면 None
    """
    goal = getattr(crew, 'goal', None)
    if not goal:
        return None

    week_start, week_end = _week_range()
    member_user_ids = list(
        crew.members.values_list('users_id', flat=True)
    )
    total = EarnRecord.objects.filter(
        users_id__in=member_user_ids,
        earn_date__range=[week_start, week_end],
    ).aggregate(total=Sum('earn_min'))['total'] or 0
    total = int(round(total))

    target = goal.target_minutes or 0
    pct = round(total / target * 100) if target > 0 else 0
    achieved = pct >= 100

    return {
        'collected_min': total,
        'collected_hm': _format_hm(total),
        'target_min': target,
        'target_hm': _format_hm(target),
        'percent': pct,
        'percent_capped': min(pct, 100),   # 바 너비용 (100 넘어도 안 넘치게)
        'achieved': achieved,
    }

def _is_member(user, crew):
    """해당 유저가 이 크루의 멤버인지 확인."""
    return CrewMember.objects.filter(crew=crew, users=user).exists()


def _process_join(request, crew):
    """크루 참여 공통 처리. 성공하면 True, 실패하면 False + 메시지."""
    # 이미 가입한 크루인지
    if CrewMember.objects.filter(crew=crew, users=request.user).exists():
        messages.info(request, '이미 이 크루의 멤버예요.')
        return True   # 이미 멤버니 상세로 보내면 됨

    # 정원(6명) 초과
    if crew.is_full:
        messages.error(request, '이 크루는 정원이 다 찼어요 (6/6).')
        return False

    # 통과 → 멤버 등록 + 활성 전환
    CrewMember.objects.create(crew=crew, users=request.user)
    crew.refresh_status()
    messages.success(request, f'"{crew.name}" 크루에 참여했어요!')
    return True


# ── 뷰 ──

@login_required
def crew_create(request):
    if request.method == 'POST':
        form = CrewCreateForm(request.POST)
        if form.is_valid():
            crew = form.save(commit=False)
            # 화면에 보였던 코드를 그대로 사용 (없으면 새로 생성)
            crew.invite_code = request.POST.get('invite_code') or generate_invite_code()
            crew.owner = request.user
            crew.save()
            CrewMember.objects.create(crew=crew, users=request.user)
            return redirect('crew:detail', crew_id=crew.id)
    else:
        form = CrewCreateForm()

    # 만들기 화면 진입 시, 미리 보여줄 코드 생성
    preview_code = generate_invite_code()
    return render(request, 'crew/crew_create.html', {
        'form': form,
        'preview_code': preview_code,
    })


@login_required
def crew_detail(request, crew_id):
    crew = get_object_or_404(Crew, id=crew_id)

    if not _is_member(request.user, crew):
        messages.error(request, '그 크루의 멤버가 아니에요.')
        return redirect('crew:list')

    sort = request.GET.get('sort', 'contribution')
    members = _sorted_members_with_contribution(crew, sort)
    goal_progress = _goal_progress(crew)

    return render(request, 'crew/crew_detail.html', {
        'crew': crew,
        'members': members,
        'member_count': len(members),
        'goal': getattr(crew, 'goal', None),
        'goal_progress': goal_progress,
        'sort': sort,
    })


@login_required
def crew_list(request):
    my_memberships = (
        CrewMember.objects
        .filter(users=request.user)
        .select_related('crew')
        .order_by('-joined_date')
    )
    crews = [m.crew for m in my_memberships]
    return render(request, 'crew/crew_list.html', {'crews': crews})


@login_required
def crew_join(request):
    if request.method == 'POST':
        form = CrewJoinForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['invite_code']
            crew = Crew.objects.filter(invite_code=code).first()
            if crew is None:
                messages.error(request, '그런 초대 코드의 크루가 없어요.')
                return redirect('crew:list')          # ← 목록으로

            ok = _process_join(request, crew)
            if ok:
                return redirect('crew:detail', crew_id=crew.id)
            return redirect('crew:list')              # ← 실패해도 목록으로
        else:
            messages.error(request, '초대 코드를 입력해주세요.')
            return redirect('crew:list')              # ← 빈 입력도 목록으로

    # GET으로 직접 오면 그냥 목록으로 (이제 crew_join 페이지 안 씀)
    return redirect('crew:list')


@login_required
def crew_join_by_link(request, invite_code):
    crew = Crew.objects.filter(invite_code=invite_code.upper()).first()

    if crew is None:
        messages.error(request, '유효하지 않은 초대 링크예요.')
        return redirect('crew:list')

    if request.method == 'POST':
        ok = _process_join(request, crew)
        if ok:
            return redirect('crew:detail', crew_id=crew.id)
        return redirect('crew:list')

    already_member = CrewMember.objects.filter(crew=crew, users=request.user).exists()
    return render(request, 'crew/crew_join_confirm.html', {
        'crew': crew,
        'already_member': already_member,
    })


@login_required
def crew_leave(request, crew_id):
    crew = get_object_or_404(Crew, id=crew_id)

    if request.method == 'POST':
        membership = CrewMember.objects.filter(crew=crew, users=request.user).first()
        if not membership:
            messages.info(request, '이미 이 크루의 멤버가 아니에요.')
            return redirect('crew:list')

        was_owner = (crew.owner_id == request.user.id)
        membership.delete()

        remaining = CrewMember.objects.filter(crew=crew).order_by('joined_date')

        if not remaining.exists():
            crew_name = crew.name
            crew.delete()
            messages.success(request, f'"{crew_name}" 크루에서 나왔고, 마지막 멤버라 크루가 사라졌어요.')
            return redirect('crew:list')

        if was_owner:
            new_owner_membership = remaining.first()
            crew.owner = new_owner_membership.users
            crew.save(update_fields=['owner'])
            messages.success(
                request,
                f'"{crew.name}" 크루에서 나왔어요. 새 크루장은 {new_owner_membership.users}님이에요.'
            )
        else:
            messages.success(request, f'"{crew.name}" 크루에서 나왔어요.')

        return redirect('crew:list')

    if not _is_member(request.user, crew):
        messages.info(request, '이미 이 크루의 멤버가 아니에요.')
        return redirect('crew:list')

    member_count = CrewMember.objects.filter(crew=crew).count()
    is_last_member = (member_count == 1)
    return render(request, 'crew/crew_leave.html', {
        'crew': crew,
        'is_last_member': is_last_member,
    })


@login_required
def crew_members_api(request, crew_id):
    """멤버 목록을 JSON으로 반환 (폴링용). crew_detail과 동일 정렬·기여도."""
    crew = get_object_or_404(Crew, id=crew_id)

    if not _is_member(request.user, crew):
        return JsonResponse({'error': 'forbidden'}, status=403)

    sort = request.GET.get('sort', 'contribution')
    members = _sorted_members_with_contribution(crew, sort)

    data = {
        'status': crew.get_status_display(),
        'member_count': len(members),
        'max_members': crew.MAX_MEMBERS,
        'owner_id': crew.owner_id,
        'members': [
            {
                'id': m.id,
                'name': str(m.users),
                'is_owner': (m.users_id == crew.owner_id),
                'contribution_pct': m.contribution_pct,
                'contribution_hm': m.contribution_hm,
                'feed_text': m.feed_text,
                'is_top': (i == 0 and m.contribution > 0),   # 1등(기여>0)만 초록
            }
            for i, m in enumerate(members)
        ],
    }
    return JsonResponse(data)

@login_required
def crew_rename(request, crew_id):
    crew = get_object_or_404(Crew, id=crew_id)

    # 크루장만 이름을 바꿀 수 있음
    if crew.owner_id != request.user.id:
        messages.error(request, '크루장만 이름을 바꿀 수 있어요.')
        return redirect('crew:detail', crew_id=crew.id)

    if request.method == 'POST':
        form = CrewRenameForm(request.POST, instance=crew)
        if form.is_valid():
            form.save()
            messages.success(request, '크루 이름을 바꿨어요.')
            return redirect('crew:detail', crew_id=crew.id)
    else:
        form = CrewRenameForm(instance=crew)

    return render(request, 'crew/crew_rename.html', {'crew': crew, 'form': form})

@login_required
def crew_create(request):
    created_crew = None

    if request.method == 'POST':
        form = CrewCreateForm(request.POST)
        if form.is_valid():
            crew = form.save(commit=False)
            crew.invite_code = generate_invite_code()
            crew.owner = request.user
            crew.save()
            CrewMember.objects.create(crew=crew, users=request.user)

            # 목표 생성 (시간 → 분 변환)
            CrewGoal.objects.create(
                crew=crew,
                target_minutes=form.cleaned_data['target_hours'] * 60,
                reward_text=form.cleaned_data['reward_text'],
            )
            created_crew = crew          # 만든 후 코드 보여주기용
            form = CrewCreateForm()
    else:
        form = CrewCreateForm()

    return render(request, 'crew/crew_create.html', {
        'form': form,
        'created_crew': created_crew,
    })

@login_required
def crew_manage(request, crew_id):
    crew = get_object_or_404(Crew, id=crew_id)

    # 크루장만 접근 가능
    if crew.owner_id != request.user.id:
        messages.error(request, '크루장만 관리할 수 있어요.')
        return redirect('crew:detail', crew_id=crew.id)

    goal = getattr(crew, 'goal', None)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'rename':
            new_name = request.POST.get('name', '').strip()
            if new_name:
                crew.name = new_name
                crew.save(update_fields=['name'])
                messages.success(request, '크루 이름을 바꿨어요.')

        elif action == 'goal':
            target_hours = request.POST.get('target_hours')
            reward_text = request.POST.get('reward_text', '')
            if goal:
                goal.target_minutes = int(target_hours) * 60
                goal.reward_text = reward_text
                goal.save()
            else:
                CrewGoal.objects.create(
                    crew=crew,
                    target_minutes=int(target_hours) * 60,
                    reward_text=reward_text,
                )
            messages.success(request, '목표를 저장했어요.')

        return redirect('crew:manage', crew_id=crew.id)

    members = _sorted_members_with_contribution(crew, sort='contribution')
    return render(request, 'crew/crew_manage.html', {
        'crew': crew,
        'goal': goal,
        'members': members,
        'member_count': len(members),
    })

@login_required
def crew_kick(request, crew_id, member_id):
    crew = get_object_or_404(Crew, id=crew_id)

    # 크루장만 내보낼 수 있음
    if crew.owner_id != request.user.id:
        messages.error(request, '크루장만 멤버를 내보낼 수 있어요.')
        return redirect('crew:detail', crew_id=crew.id)

    if request.method == 'POST':
        membership = CrewMember.objects.filter(crew=crew, id=member_id).first()

        # 없는 멤버거나, 크루장 자신을 내보내려 하면 막기
        if not membership:
            messages.error(request, '그런 멤버가 없어요.')
        elif membership.users_id == crew.owner_id:
            messages.error(request, '크루장은 내보낼 수 없어요.')
        else:
            kicked_name = str(membership.users)
            membership.delete()
            # 초대 코드 재발급 (내보낸 사람이 옛 코드로 다시 못 들어오게)
            crew.invite_code = generate_invite_code()
            crew.save(update_fields=['invite_code'])
            messages.success(request, f'{kicked_name}님을 내보냈어요. 초대 코드가 새로 발급됐어요.')

    return redirect('crew:manage', crew_id=crew.id)

@login_required
def crew_member_detail(request, crew_id, member_id):
    crew = get_object_or_404(Crew, id=crew_id)

    # 크루 멤버만 볼 수 있음
    if not _is_member(request.user, crew):
        messages.error(request, '그 크루의 멤버가 아니에요.')
        return redirect('crew:list')

    membership = get_object_or_404(CrewMember, id=member_id, crew=crew)

    return render(request, 'crew/crew_member_detail.html', {
        'crew': crew,
        'membership': membership,
    })

@login_required
def crew_cheer(request, crew_id, member_id):
    """멤버에게 응원 보내기. FeedEvent(cheer) 생성."""
    crew = get_object_or_404(Crew, id=crew_id)

    if not _is_member(request.user, crew):
        messages.error(request, '그 크루의 멤버가 아니에요.')
        return redirect('crew:list')

    if request.method == 'POST':
        target_membership = get_object_or_404(CrewMember, id=member_id, crew=crew)
        target_user = target_membership.users

        # 자기 자신 응원 방지
        if target_user == request.user:
            messages.info(request, '자기 자신은 응원할 수 없어요.')
            return redirect('crew:member_detail', crew_id=crew.id, member_id=member_id)

        from crew.models import FeedEvent
        FeedEvent.objects.create(
            crew=crew,
            actor=request.user,
            target=target_user,
            event_type=FeedEvent.EventType.CHEER,
            message=f"{request.user}님이 {target_user}님을 응원했어요",
        )
        messages.success(request, f'{target_user}님에게 응원을 보냈어요!')
        return redirect('crew:member_detail', crew_id=crew.id, member_id=member_id)

    return redirect('crew:member_detail', crew_id=crew.id, member_id=member_id)