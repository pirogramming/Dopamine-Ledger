from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import SpendRecordForm, EarnRecordForm
from .models import SpendRecord, EarnRecord
from .services import close_today, get_today_record_summary
from budget.services import get_current_balance

from budget.services import (
    get_week_summary,
    get_today_records,
    attach_value_displays,
    format_minutes_display,
    format_unit_display,
)

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
            return redirect('ledger:main_progress')
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
            return redirect('ledger:main_progress')
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
    balance = get_current_balance(request.user)

    can_close = (
        summary["has_earn_record"]
        or summary["has_spend_record"]
    )
    error_message = None

    if request.method == "POST":

        try:
            close_today(request.user)
            return redirect("ledger:daily_close")

        except ValueError as error:
            error_message = str(error)

    context = {
        **summary,
        "balance": balance,
        "can_close": can_close,
        "streak_days": request.user.streak_days,
        "error_message": error_message,
        "active_tab": "deadline",
    }

    return render(
        request,
        "ledger/daily_close.html",
        context,
    )
@login_required
def main_progress(request):
    """홈 — 시간으로 보기."""
    summary = get_week_summary(request.user)
    records = attach_value_displays(
        get_today_records(request.user), mode='minutes',
    )
    context = {
        **summary,
        'balance_display':  format_minutes_display(summary['balance']),
        'budget_display':   format_minutes_display(summary['budget']),
        'spent_display':    format_minutes_display(summary['spent']),
        'earned_display':   format_minutes_display(summary['earned']),
        'budget_desc': (
            f"이번 주 예산 {format_minutes_display(summary['budget'])} 중 "
            f"{format_minutes_display(summary['spent'])} 사용"
        ),
        'today_records': records,
        'today_record_count': len(records),
    }
    return render(request, 'ledger/main_progress.html', context)

@login_required
def main_convert(request):
    """홈 — 변환해서 보기.
    큰 잔액만 conversion_base로 환산해서 크게 표시하고,
    이번 주 예산/사용/적립 요약은 main_progress와 동일하게 분(시간) 포맷으로 표시.
    오늘의 기록도 main_progress와 동일하게 분 단위로 표시."""
    user = request.user
    summary = get_week_summary(user)
    base = user.conversion_base
    unit = user.conversion_unit or ''
    activity = user.converting_activity or '환산 활동'

    records = attach_value_displays(
        get_today_records(user), mode='minutes',   # 'unit' → 'minutes'
    )
    context = {
        **summary,
        'balance_display':  format_unit_display(summary['balance'], base, unit),
        'budget_display':   format_minutes_display(summary['budget']),
        'spent_display':    format_minutes_display(summary['spent']),
        'earned_display':   format_minutes_display(summary['earned']),
        'budget_desc': (
            f"이번 주 예산 {format_minutes_display(summary['budget'])} 중 "
            f"{format_minutes_display(summary['spent'])} 사용"
        ),
        'converted_unit_label': f"이번 주 남은 {activity} 시간",
        'today_records': records,
        'today_record_count': len(records),
    }
    return render(request, 'ledger/main_convert.html', context)
