from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import SpendRecordForm, EarnRecordForm
from .models import SpendRecord, EarnRecord

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
    큰 값은 잔액을 활동 단위로 환산해서 '활동명 + 수치' 형태로.
    진행률 위 설명은 2줄(둘째 줄 강조). 예산/사용/적립 요약은 표시하지 않음."""
    user = request.user
    summary = get_week_summary(user)
    base = user.conversion_base
    unit = user.conversion_unit or ''
    activity = user.converting_activity or '환산 활동'

    records = attach_value_displays(
        get_today_records(user), mode='unit',
        conversion_base=base, unit_label=unit,
    )

    balance_converted = format_unit_display(summary['balance'], base, unit)
    spent_converted   = format_unit_display(summary['spent'],   base, unit)

    context = {
        **summary,
        # 큰 값 (도넛 중앙 승격) — "독서 50페이지"
        'converted_unit_label': "남은 숏폼 시간을 활동으로 바꾸면",
        'balance_display':      f"{activity} {balance_converted}",
        # 진행률 상단 설명 (2줄, 둘째 줄 강조)
        'desc_line1': f"이번 주 사용한 {format_minutes_display(summary['spent'])}은",
        'desc_line2': f"{activity} {spent_converted}에 해당해요",
        'today_records': records,
        'today_record_count': len(records),
    }
    return render(request, 'ledger/main_convert.html', context)