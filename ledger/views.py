from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import SpendRecordForm, EarnRecordForm
from .models import SpendRecord, EarnRecord
from .services import close_today, get_today_record_summary
from budget.services import get_current_balance, get_conversion_base_precise
from accounts.services import (
    calculate_grade_by_streak,
    calculate_reward_minutes,
    get_exchange_bonus_rate,
    get_league_dialogue,
    get_league_journey_data,
)

from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum
from django.http import JsonResponse

from collections import defaultdict

from django.http import HttpResponse
from .services import generate_weekly_share_card, get_category_color
from budget.services import format_unit_display

# 요일 변환용 튜플 (weekly_report)
WEEKDAYS_KR = ("월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일")

NEXT_GRADE_TARGETS = {
    'LEVEL_0': 3,
    'LEVEL_1': 7,
    'LEVEL_2': 14,
    'LEVEL_3': 30,
    'LEVEL_4': None,
}

from budget.services import (
    get_week_summary,
    get_today_activity_summary,
    get_today_record_count,
    attach_value_displays,
    format_minutes_display,
    format_unit_display,
    get_today_spent_minutes,
    get_ro_particle, 
)

@login_required
def spend_record_create(request):
    """
    지출 기록 생성 뷰.
    - GET: 빈 폼을 보여줌. 잔액이 음수면 진입 시 초과지출 경고 모달 표시(매번). 지출은 막지 않음.
    - POST: 검증 후 저장. 저장하면 홈으로 이동(마이너스 반영 확인).
    """
    if request.method == 'POST':
        form = SpendRecordForm(request.POST)
        if form.is_valid():
            # 저장 '전' 잔액을 먼저 잰다 (과예산분 계산용)
            balance_before = get_current_balance(request.user)

            instance = form.save(commit=False)
            instance.users = request.user  # 모델 필드명이 user -> users로 바뀐 것 반영
            instance.save()

            # 이 지출 중 예산을 넘긴 부분(과예산분)만 크루 피드/목표에 반영
            # 지출 전 잔액이 양수면 그만큼은 정상, 나머지가 과예산. 음수면 전액 과예산.
            duration = instance.duration_min
            positive_before = max(balance_before, Decimal('0'))
            overspend_min = max(Decimal('0'), Decimal(duration) - positive_before)

            if overspend_min > 0:
                from crew.services import create_overspend_feed
                create_overspend_feed(request.user, int(overspend_min))

            # 저장 후 홈으로 → 잔액(마이너스 포함) 갱신 확인
            return redirect('ledger:main_progress')
        # form.is_valid()가 False면 여기서 form을 새로 안 만들고
        # 에러가 담긴 form 그대로 아래 render로 넘어감 (에러 메시지 보존)
    else:
        # GET 요청 분기가 없어서 아무것도 반환 안 하던 버그 수정
        form = SpendRecordForm()

    # 지출 화면 진입 시점의 잔액이 음수면 초과지출 경고 모달 표시 (매번, 차단 아님)
    balance = get_current_balance(request.user)
    budget_exhausted = balance < 0

    return render(request, 'ledger/spend_record_form.html', {
        'form': form,
        'budget_exhausted': budget_exhausted,
    })


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

            bonus_rate = Decimal(
                str(get_exchange_bonus_rate(request.user.credit_grade))
            )
            total_rate = instance.activity.rate + bonus_rate
            instance.earn_min = Decimal(min(int(form.cleaned_data['duration_min'] * total_rate), 59))

            instance.save()

            # 크루 피드에 벌이 이벤트 생성 (내가 속한 모든 크루)
            from crew.services import create_earn_feed
            create_earn_feed(
                request.user,
                instance.activity.activity_type,
                instance.earn_min,
            )

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
def weekly_report(request):
    user = request.user
    today = timezone.localdate()

    # 1. 날짜 범위 산출
    this_start = today - timedelta(days=today.weekday())
    this_end = this_start + timedelta(days=6)

    last_start = this_start - timedelta(days=7)
    last_end = this_start - timedelta(days=1)

    # 2. 숏폼 지출 집계
    this_spend_qs = SpendRecord.objects.filter(
        users=user, spend_date__range=[this_start, this_end]
    )
    last_spend_qs = SpendRecord.objects.filter(
        users=user, spend_date__range=[last_start, last_end]
    )

    this_spend_total = this_spend_qs.aggregate(total=Sum('duration_min'))['total'] or 0
    last_spend_total = last_spend_qs.aggregate(total=Sum('duration_min'))['total'] or 0

    # 3. 활동 적립 집계
    this_earn_qs = EarnRecord.objects.filter(
        users=user, earn_date__range=[this_start, this_end]
    )
    last_earn_qs = EarnRecord.objects.filter(
        users=user, earn_date__range=[last_start, last_end]
    )

    this_earn_total = this_earn_qs.aggregate(total=Sum('earn_min'))['total'] or 0
    last_earn_total = last_earn_qs.aggregate(total=Sum('earn_min'))['total'] or 0

    # 4. 차이 수치 계산
    spend_diff = this_spend_total - last_spend_total
    earn_diff = this_earn_total - last_earn_total

    # 5. 수치 반올림 처리
    this_spend_int = int(round(this_spend_total))
    last_spend_int = int(round(last_spend_total))
    spend_diff_int = int(round(spend_diff))
    this_earn_total_int = int(round(this_earn_total))
    earn_diff_int = int(round(earn_diff))

    # 5. 활동별 집계
    this_activity_map = {
        item['activity__activity_type']: int(round(item['total'] or 0))
        for item in this_earn_qs.values('activity__activity_type').annotate(total=Sum('earn_min'))
    }
    last_activity_map = {
        item['activity__activity_type']: int(round(item['total'] or 0))
        for item in last_earn_qs.values('activity__activity_type').annotate(total=Sum('earn_min'))
    }

    # 이번 주 카테고리별 비중 데이터
    category_total = sum(this_activity_map.values())

    category_breakdown = []

    if category_total > 0:
        # 이번 주에 해당 활동이 처음 기록된 시간 순서
        first_record_order = {}

        for earn in this_earn_qs.order_by("created_at"):
            activity_name = earn.activity.activity_type

            if activity_name not in first_record_order:
                first_record_order[activity_name] = earn.created_at

        # 최초 기록 순서대로 카테고리 정렬
        ordered_activity_names = sorted(
            this_activity_map.keys(),
            key=lambda name: first_record_order[name]
        )

        for idx, activity_name in enumerate(ordered_activity_names):
            minutes = this_activity_map[activity_name]

            category_breakdown.append({
                "name": activity_name,
                "minutes": minutes,
                "percent": round((minutes / category_total) * 100, 1),
                "color": get_category_color(idx),
            })

    best_activity = None
    max_increase = 0

    for act_name, this_min in this_activity_map.items():
        last_min = last_activity_map.get(act_name, 0)
        increase = this_min - last_min
        if increase > max_increase:
            max_increase = increase
            best_activity = act_name

    # --------------------------------------------------
    # 6. 칭찬 문구 조건 분기 (지난주 데이터 부재 시 예외 처리 최우선)
    # --------------------------------------------------
    is_no_last_data = (last_spend_total == 0) and (last_earn_total == 0)

    if is_no_last_data:
        if this_earn_total_int > 0:
            total_hrs = int(this_earn_total_int // 60)
            total_mins = int(this_earn_total_int % 60)
            earn_str = f"{total_hrs}시간 {total_mins}분" if total_hrs > 0 else f"{total_mins}분"
            praise_message = f"이번 주 총 {earn_str} 동안 멋지게 활동하며 시간을 벌었어요!"
        else:
            praise_message = "꾸준히 기록하며 도파민을 관리해 보아요!"

    elif best_activity and max_increase > 0:
        this_hrs = int(this_activity_map[best_activity] // 60)
        this_mins = int(this_activity_map[best_activity] % 60)
        inc_hrs = int(max_increase // 60)
        inc_mins = int(max_increase % 60)
        
        this_str = f"{this_hrs}시간 {this_mins}분" if this_hrs > 0 else f"{this_mins}분"
        inc_str = f"{inc_hrs}시간 {inc_mins}분" if inc_hrs > 0 else f"{inc_mins}분"
        
        praise_message = f"이번 주 {best_activity} {this_str}, 지난주보다 {inc_str} 늘었어요!"

    elif spend_diff_int < 0:
        praise_message = f"이번 주는 지난주보다 숏폼을 {abs(spend_diff_int)}분 줄였어요!"

    else:
        praise_message = "꾸준히 기록하며 도파민을 관리해 보아요!"

    # --------------------------------------------------
    # 7. 이번 주 활동 내역 날짜별 그룹화 (history_by_date 생성)
    # --------------------------------------------------
    raw_items = []

    # 1. 수입 레코드 수집
    for earn in this_earn_qs.select_related('activity'):
        local_time = timezone.localtime(earn.created_at)
        time_str = local_time.strftime("%p %I:%M").replace("AM" ,"오전").replace("PM", "오후")

        record_date = local_time.date()
        weekday_kr = WEEKDAYS_KR[record_date.weekday()]
        date_str = f"{record_date.strftime('%Y년 %m월 %d일')} {weekday_kr}"

        total_minutes = int(round(float(earn.earn_min)))
        hours = total_minutes // 60
        minutes = total_minutes % 60

        if hours > 0 and minutes > 0:
            amount_text = f"{hours}시간 {minutes}분"
        elif hours > 0:
            amount_text = f"{hours}시간"
        else:
            amount_text = f"{minutes}분"

        raw_items.append({
            "dt_key": earn.created_at,
            "date_str": date_str,
            "data": {
                "type": "earn",
                "title": f"{earn.activity.activity_type} 완료",
                "time": time_str,
                "amount": amount_text
            }
        })

    # 2. 지출 레코드 수집
    for spend in this_spend_qs:
        local_time = timezone.localtime(spend.created_at)
        time_str = local_time.strftime("%p %I:%M").replace("AM", "오전").replace("PM", "오후")

        record_date = local_time.date()
        weekday_kr = WEEKDAYS_KR[record_date.weekday()]
        date_str = f"{record_date.strftime('%Y년 %m월 %d일')} {weekday_kr}"

        total_minutes = int(round(float(spend.duration_min)))

        hours = total_minutes // 60
        minutes = total_minutes % 60

        if hours > 0 and minutes > 0:
            amount_text = f"{hours}시간 {minutes}분"
        elif hours > 0:
            amount_text = f"{hours}시간"
        else:
            amount_text = f"{minutes}분"
        
        raw_items.append({
            "dt_key": spend.created_at,
            "date_str": date_str,
            "data": {
                "type": "spend",
                "title": "숏폼 지출",
                "time": time_str,
                "amount": amount_text
            }
        })

    # 3. 전체 아이템 정렬화
    raw_items.sort(key=lambda x: x["dt_key"], reverse=True)

    date_grouped = defaultdict(list)
    for item in raw_items:
        date_grouped[item["date_str"]].append(item["data"])

    history_by_date = [
        {
            "date": date_key,
            "items": items
        }
        for date_key, items in date_grouped.items()
    ]

    return JsonResponse(
        {
            "praise_message": praise_message,
            "this_spend_min": this_spend_int,
            "last_spend_min": last_spend_int,
            "spend_diff_min": spend_diff_int,
            "this_earn_min": this_earn_total_int,
            "earn_diff_min": earn_diff_int,
            "category_breakdown": category_breakdown,
            "history_by_date": history_by_date,
        },
        json_dumps_params={'ensure_ascii': False}
    )

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
    is_closed = False

    if request.method == "POST":
        try:
            close_today(request.user)
            request.user.credit_grade = calculate_grade_by_streak(request.user.streak_days)
            request.user.save()

            is_closed = True

            request.user.refresh_from_db()      # streak_days 갱신값 반영
            from crew.services import create_close_feed
            create_close_feed(request.user, request.user.streak_days)
            return redirect("ledger:daily_close")
        except ValueError as error:
            error_message = str(error)

    is_closed = summary.get("is_closed", False)

    context = {
        **summary,
        "balance": balance,
        "can_close": can_close,
        "streak_days": request.user.streak_days,
        "error_message": error_message,
        "active_tab": "deadline",
        "credit_grade": request.user.credit_grade,
        "grade_name": request.user.grade_name,
        "bonus_rate_percent": int(
            get_exchange_bonus_rate(request.user.credit_grade) * 100
        ),
        "closure_character_url": request.user.closure_character_url,
        "profile_character_url": request.user.profile_character_url,
        "league_dialogue": get_league_dialogue(
            request.user.credit_grade, is_closed=is_closed
        ),
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
        get_today_activity_summary(request.user), mode='minutes'
    )

    target_days = NEXT_GRADE_TARGETS.get(request.user.credit_grade)
    if target_days:
        days_to_next_grade = max(target_days - request.user.streak_days, 0)
    else:
        days_to_next_grade = None  # 최고 등급일 때

    context = {
        **summary,
        'balance_display':  format_minutes_display(summary['balance']),
        'budget_display':   format_minutes_display(summary['budget']),
        'spent_display':    format_minutes_display(summary['spent']),
        'earned_display':   format_minutes_display(summary['earned']),
        'budget_desc': (
            f"이번 주 예산 {format_minutes_display(summary['budget'] + summary['earned'])} 중 "
            f"{format_minutes_display(summary['spent'])} 사용"
        ),
        'today_records': records,
        'today_record_count': get_today_record_count(request.user),
        'active_tab': 'home',
        'credit_grade': request.user.credit_grade,
        'grade_name': request.user.grade_name,
        'streak_days': request.user.streak_days,
        'days_to_next_grade': days_to_next_grade,
        'bonus_rate_percent': int(
            get_exchange_bonus_rate(request.user.credit_grade) * 100
        ),
    }
    return render(request, 'ledger/main_progress.html', context)

@login_required
def main_convert(request):
    """홈 — 변환해서 보기.
    큰 값: 이번 주 지출 시간을 환산.
    진행률 설명: 오늘 지출한 시간을 환산해서 2줄(둘째 줄 강조)로 표시."""
    user = request.user
    summary = get_week_summary(user)
    base = get_conversion_base_precise(user)
    unit = user.conversion_unit or ''
    activity = user.converting_activity or '환산 활동'

    today_spent = get_today_spent_minutes(user)

    records = attach_value_displays(
        get_today_activity_summary(user), mode='minutes',
    )

    target_days = NEXT_GRADE_TARGETS.get(request.user.credit_grade)
    if target_days:
        days_to_next_grade = max(target_days - request.user.streak_days, 0)
    else:
        days_to_next_grade = None  # 최고 등급일 때

    context = {
        **summary,
        'balance_display':  format_unit_display(summary['spent'], base, unit),
        'budget_display':   format_minutes_display(summary['budget']),
        'spent_display':    format_minutes_display(summary['spent']),
        'earned_display':   format_minutes_display(summary['earned']),
        'converted_unit_label': f"이번 주 사용한 시간을 {activity}{get_ro_particle(activity)} 바꾸면",
        # 진행률 위 2줄 설명 (오늘 지출 기준)
        'desc_line1': f"오늘 숏폼에 사용한 {format_minutes_display(today_spent)}은",
        'desc_line2': f"{activity} {format_unit_display(today_spent, base, unit)}에 해당해요",
        'today_records': records,
        'today_record_count': get_today_record_count(user),
        'active_tab': 'home',
        'credit_grade': request.user.credit_grade,
        'grade_name': request.user.grade_name,
        'streak_days': request.user.streak_days,
        'days_to_next_grade': days_to_next_grade,
        'bonus_rate_percent': int(
            get_exchange_bonus_rate(request.user.credit_grade) * 100
        ),
    }
    return render(request, 'ledger/main_convert.html', context)


"""@login_required
def weekly_share_card(request):
    
#    주간 결산 공유 카드 이미지(PNG)를 발행한다.
#    weekly_report와 동일한 집계 로직을 쓰되, 화면이 아닌 이미지로 응답.
    
    user = request.user

    # 1) 이번 주 / 지난주 날짜 범위
    # weekly_report와 동일하게 로컬타임 기준. (weekly_report의 UTC 버그는 PM이 별도 수정 중)
    today = timezone.localdate()
    this_start = today - timedelta(days=today.weekday())
    this_end = this_start + timedelta(days=6)
    last_start = this_start - timedelta(days=7)
    last_end = this_start - timedelta(days=1)

    # 2) 집계 (weekly_report와 같은 방식)
    this_spend = SpendRecord.objects.filter(
        users=user, spend_date__range=[this_start, this_end]
    ).aggregate(total=Sum('duration_min'))['total'] or 0

    last_spend = SpendRecord.objects.filter(
        users=user, spend_date__range=[last_start, last_end]
    ).aggregate(total=Sum('duration_min'))['total'] or 0

    this_earn = EarnRecord.objects.filter(
        users=user, earn_date__range=[this_start, this_end]
    ).aggregate(total=Sum('earn_min'))['total'] or 0

    # 3) 주차 라벨 & 닉네임
    week_label = (
        f"{this_start.strftime('%Y년 %m월 %d일')} ~ "
        f"{this_end.strftime('%m월 %d일')}"
    )
    nickname = (
        getattr(user, 'nickname', None)
        or getattr(user, 'username', None)
        or '사용자'
    )

    # 4) 대체재 환산 문구 만들기
    #    - 사용자가 온보딩에서 환산 활동을 설정했을 때만 넣음
    #    - 지출 시간을 기준으로 "= 책 0.8권 / 숏폼에 쓴 만큼의 시간" 두 줄 구성
    conversion_base = getattr(user, 'conversion_base', None)
    conversion_unit = getattr(user, 'conversion_unit', '') or ''
    converting_activity = getattr(user, 'converting_activity', '') or ''

    alt_text = ""
    if conversion_base and conversion_base > 0 and this_spend > 0:
        # format_unit_display는 "0.8권" 같은 문자열을 만들어줌 (Decimal → 소수점 1자리 자동)
        converted_str = format_unit_display(
            int(round(this_spend)), conversion_base, conversion_unit,
        )
        alt_text = {
            "converted": f"{converting_activity} {converted_str}",
            "context": "숏폼에 쓴 만큼의 시간",
        }

    # 5) 이미지 생성
    png_bytes = generate_weekly_share_card(
        nickname=nickname,
        this_spend_min=int(round(this_spend)),
        this_earn_min=int(round(this_earn)),
        spend_diff_min=int(round(this_spend - last_spend)),
        week_label=week_label,
        alt_text=alt_text,   # ← dict로 전달 (빈 값이면 카드에 안 그려짐)
    )

    # 6) PNG로 응답 (다운로드 강제)
    response = HttpResponse(png_bytes, content_type="image/png")
    filename = f"weekly-report-{this_start.isoformat()}.png"
    # inline: 브라우저가 다운로드 대화상자를 띄우지 않음 (JS가 처리)
    # 그래도 filename은 남겨둠 — JS 폴백에서 다운로드할 때 이 이름 씀
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    response['Cache-Control'] = 'no-store'
    return response"""

@login_required
def league_journey(request):
    """리그 여정(로드맵) 화면 뷰"""
    journey_data = get_league_journey_data(request.user)

    context = {
        **journey_data,
        'closure_character_url': request.user.closure_character_url,
        'active_tab': 'deadline', # 필요에 따른 활성 탭
    }
    return render(request, 'ledger/league_journey.html', context)

@login_required
def weekly_share_card(request):
    """주간 결산 공유 카드 이미지(PNG)를 발행한다."""
    user = request.user

    # 1) 이번 주 / 지난주 날짜 범위
    today = timezone.localdate()
    this_start = today - timedelta(days=today.weekday())
    this_end = this_start + timedelta(days=6)
    last_start = this_start - timedelta(days=7)
    last_end = this_start - timedelta(days=1)

    # 2) 집계
    this_spend = SpendRecord.objects.filter(
        users=user, spend_date__range=[this_start, this_end]
    ).aggregate(total=Sum('duration_min'))['total'] or 0

    last_spend = SpendRecord.objects.filter(
        users=user, spend_date__range=[last_start, last_end]
    ).aggregate(total=Sum('duration_min'))['total'] or 0

    this_earn = EarnRecord.objects.filter(
        users=user, earn_date__range=[this_start, this_end]
    ).aggregate(total=Sum('earn_min'))['total'] or 0

    # 지난주 수입도 추가 (새 카드 디자인에서 수입 증감 표시용)
    last_earn = EarnRecord.objects.filter(
        users=user, earn_date__range=[last_start, last_end]
    ).aggregate(total=Sum('earn_min'))['total'] or 0

    # 3) 주차 라벨 & 닉네임
    week_label = (
        f"{this_start.strftime('%Y년 %m월 %d일')} ~ "
        f"{this_end.strftime('%m월 %d일')}"
    )
    nickname = (
        getattr(user, 'nickname', None)
        or getattr(user, 'username', None)
        or '사용자'
    )

    # 4) 대체재 환산 (수입/지출 각각)
    conversion_base = get_conversion_base_precise(user)
    conversion_unit = getattr(user, 'conversion_unit', '') or ''
    converting_activity = getattr(user, 'converting_activity', '') or ''

    earn_alt = ""
    spend_alt = ""
    if conversion_base and conversion_base > 0:
        if this_earn > 0:
            earn_converted = format_unit_display(
                int(round(this_earn)), conversion_base, conversion_unit,
            )
            earn_alt = f"{converting_activity} {earn_converted}"
        if this_spend > 0:
            spend_converted = format_unit_display(
                int(round(this_spend)), conversion_base, conversion_unit,
            )
            spend_alt = f"{converting_activity} {spend_converted}"

    # 5) 이미지 생성
    png_bytes = generate_weekly_share_card(
        nickname=nickname,
        week_label=week_label,
        this_earn_min=int(round(this_earn)),
        this_spend_min=int(round(this_spend)),
        earn_diff_min=int(round(this_earn - last_earn)),
        spend_diff_min=int(round(this_spend - last_spend)),
        earn_alt=earn_alt,
        spend_alt=spend_alt,
    )

    response = HttpResponse(png_bytes, content_type="image/png")
    filename = f"weekly-report-{this_start.isoformat()}.png"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    response['Cache-Control'] = 'no-store'
    return response