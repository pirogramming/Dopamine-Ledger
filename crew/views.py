# crew/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.http import JsonResponse

from .forms import CrewCreateForm, CrewJoinForm
from .models import Crew, CrewMember, generate_invite_code


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
            crew.invite_code = generate_invite_code()
            crew.owner = request.user
            crew.save()
            CrewMember.objects.create(crew=crew, users=request.user)
            return redirect('crew:detail', crew_id=crew.id)
    else:
        form = CrewCreateForm()

    return render(request, 'crew/crew_create.html', {'form': form})


@login_required
def crew_detail(request, crew_id):
    crew = get_object_or_404(Crew, id=crew_id)

    if not _is_member(request.user, crew):
        messages.error(request, '그 크루의 멤버가 아니에요.')
        return redirect('crew:list')

    members = crew.members.select_related('users')
    return render(request, 'crew/crew_detail.html', {
        'crew': crew,
        'members': members,
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
                return render(request, 'crew/crew_join.html', {'form': form})

            ok = _process_join(request, crew)
            if ok:
                return redirect('crew:detail', crew_id=crew.id)
            return render(request, 'crew/crew_join.html', {'form': form})
    else:
        form = CrewJoinForm()

    return render(request, 'crew/crew_join.html', {'form': form})


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
                'name': str(m.users),
                'is_owner': (m.users_id == crew.owner_id),
                'joined': m.joined_date.strftime('%Y년 %m월 %d일'),
            }
            for m in members
        ],
    }
    return JsonResponse(data)