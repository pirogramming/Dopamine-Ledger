# crew/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.http import JsonResponse

from .forms import CrewCreateForm, CrewJoinForm, CrewRenameForm
from .models import Crew, CrewMember, CrewGoal, generate_invite_code, assign_character


# ── 헬퍼 ──

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
    CrewMember.objects.create(
        crew=crew,
        users=request.user,
        character=assign_character(crew),   # ← 안 쓰이는 가장 작은 번호
    )
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
            CrewMember.objects.create(
                crew=crew,
                users=request.user,
                character=assign_character(crew),   # ← 빈 번호 배정 (첫 멤버라 1)
            )
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

    members = crew.members.select_related('users')

    goal = getattr(crew, 'goal', None)

    return render(request, 'crew/crew_detail.html', {
        'crew': crew,
        'members': members,
        'goal': goal,
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
    """멤버 목록을 JSON으로 반환 (폴링용)."""
    crew = get_object_or_404(Crew, id=crew_id)

    if not _is_member(request.user, crew):
        return JsonResponse({'error': 'forbidden'}, status=403)

    members = crew.members.select_related('users').order_by('joined_date')

    data = {
        'status': crew.get_status_display(),
        'member_count': crew.member_count,
        'max_members': crew.MAX_MEMBERS,
        'owner_id': crew.owner_id,
        'members': [
            {
                'id': m.id,
                'name': str(m.users),
                'is_owner': (m.users_id == crew.owner_id),
                'character': m.character_image,
            }
            for m in members
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

    members = crew.members.select_related('users')
    return render(request, 'crew/crew_manage.html', {
        'crew': crew,
        'goal': goal,
        'members': members,
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