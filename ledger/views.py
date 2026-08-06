from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import SpendRecordForm, EarnRecordForm
from .models import SpendRecord, EarnRecord
from .services import close_today, get_today_record_summary


@login_required
def spend_record_create(request):
    """
    지출 기록 생성 뷰.
    - GET: 빈 폼을 보여줌
    - POST: 검증 후 저장. user는 폼 필드로 노출하지 않고 request.user로 직접 채움(다른 사람 이름으로 기록 남기는 것 방지)
    """
    if request.method == 'POST':
        form = SpendRecordForm(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.users = request.user  # 모델 필드명이 user -> users로 바뀐 것 반영
            instance.save()
            # Post-Redirect-Get: 새로고침 시 중복 저장 방지
            return redirect('ledger:record_choice')
        # form.is_valid()가 False면 여기서 form을 새로 안 만들고
        # 에러가 담긴 form 그대로 아래 render로 넘어감 (에러 메시지 보존)
    else:
        # GET 요청 분기가 없어서 아무것도 반환 안 하던 버그 수정
        form = SpendRecordForm()

    return render(request, 'ledger/spend_record_form.html', {'form': form})


@login_required
def spend_record_list(request):
    """
    지출 기록 목록 조회 뷰.
    - 본인 기록만 조회(다른 유저 기록 노출 금지)
    - 최신순 정렬
    * 이 쿼리셋은 나중에 홈 화면에서도 최근 지출 미리보기 용도로 재사용될 수 있음 - 2주차 담당자한테 공유 예정
    """
    # 필드명이 users라서 필터 키워드도 맞춰줘야 함 (안 그러면 FieldError)
    records = SpendRecord.objects.filter(users=request.user).order_by('-spend_start')
    return render(request, 'ledger/spend_record_list.html', {'records': records})


@login_required
def earn_record_create(request):
    """
    수입 기록 생성 뷰
    - GET: entry_mode(타이머/수동입력)로 어떤 화면을 보여줄지 결정
    - POST: entry_mode에 따라 폼이 다르게 검증/계산됨
    """
    if request.method == 'POST':
        form = EarnRecordForm(request.POST, user=request.user)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.users = request.user  # user -> users
            instance.save()
            return redirect('ledger:record_choice')
        # 검증 실패 시 새 폼으로 덮어쓰지 않고 에러 담긴 form 그대로 유지
    else:
        entry_mode = request.GET.get('mode', 'manual')
        form = EarnRecordForm(initial={'entry_mode': entry_mode}, user=request.user)

    return render(request, 'ledger/earn_record_form.html', {'form': form})


@login_required
def earn_record_list(request):
    """수입 기록 목록 조회 뷰, 본인 기록만 최신순으로"""
    records = EarnRecord.objects.filter(users=request.user).order_by('-earn_start')
    return render(request, 'ledger/earn_record_list.html', {'records': records})


@login_required
def record_choice(request):
    """기록하기 진입 화면 - 지출/수입 선택만 보여주는 단순 뷰"""
    return render(request, 'ledger/record_choice.html')


@login_required
def daily_close(request):
    """오늘 기록을 확인하고 하루 마감을 처리하는 뷰"""
    summary = get_today_record_summary(request.user)
    error_message = None

    if request.method == "POST":
        no_spend_checked = request.POST.get("no_spend") == "on"

        try:
            close_today(
                request.user,
                no_spend_checked=no_spend_checked,
            )
            return redirect("ledger:daily_close")

        except ValueError as error:
            error_message = str(error)

    context = {
        **summary,
        "streak_days": request.user.streak_days,
        "error_message": error_message,
    }

    return render(
        request,
        "ledger/daily_close.html",
        context,
    )