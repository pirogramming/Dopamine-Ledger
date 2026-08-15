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
    GRADE_CONFIG,   # 캐릭터 카드 등급 정보 - 등급 기준을 여기서만 관리 (ledger에 따로 안 둠)
    GRADE_ORDER,    # 등급 순서 리스트 ['LEVEL_0', ..., 'LEVEL_4']
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

# NOTE: 예전에 여기 있던 NEXT_GRADE_TARGETS 딕셔너리는 삭제함.
# accounts.services.GRADE_CONFIG와 컷오프 기준이 중복/불일치할 위험이 있어서
# 캐릭터 카드 계산은 전부 GRADE_CONFIG/GRADE_ORDER를 그대로 참조하도록 통일 (_get_character_card_context 참고)

from budget.services import (
    get_week_summary,
    get_today_home_summary,
    get_today_record_count,
    attach_value_displays,
    format_minutes_display,
    format_unit_display,
    get_today_spent_minutes,
    get_ro_particle, 
    get_week_range,          # 추가 - 선택 날짜가 속한 주 계산용
    get_today_kst,            # 추가 - 기본 날짜(오늘)
    get_category_display,     # 추가 - 지출 카테고리 한글 표시
    SPEND_CATEGORY_ICONS,      # 추가
    EARN_ACTIVITY_ICONS,       # 추가
    DEFAULT_ICON,              # 추가
    DEFAULT_EARN_ICON,         # 추가
    KST,                       # 추가 - 시간대 계산용
)
def _get_character_card_context(user):
    """
    홈 캐릭터 카드에 필요한 값 모음.
    main_progress / main_convert 둘 다 같은 카드를 쓰므로 중복 계산 방지용으로 함수로 뺌.
 
    - 등급 컷오프(min_days)는 accounts.services.GRADE_CONFIG를 그대로 참조.
      여기서 따로 하드코딩하지 않음 (기준이 두 곳에서 어긋나는 사고 방지).
    - 캐릭터 이미지: profile용 에셋(static/images/characters/profile/)이 아직 없어서
      daily_close.html과 동일한 closure 이미지를 임시로 재사용함.
      TODO: profile 이미지 에셋 준비되면 아래 character_image_url 줄만
            user.closure_character_url → user.profile_character_url 로 교체
    """
    grade_key = user.credit_grade
    level_number = GRADE_ORDER.index(grade_key) if grade_key in GRADE_ORDER else 0
    next_index = level_number + 1

    if next_index < len(GRADE_ORDER):
        next_grade_key = GRADE_ORDER[next_index]
        next_min_days = GRADE_CONFIG[next_grade_key]['min_days']
        days_to_next_grade = max(next_min_days - user.streak_days, 0)
    else:
        days_to_next_grade = None  # 최고 등급(LEVEL_4) - 다음 등급 없음
        
    return {
        'level_number': level_number,
        'character_image_url': user.closure_character_url,  # profile 폴더 없어서 closure 재사용
        'days_to_next_grade': days_to_next_grade,
    }
    
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
    * 이 쿼리셋은 나중에 홈 화면에서도 최근 지출 미리보기 용도로 재사용될 수 있음
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
        get_today_home_summary(request.user), mode='minutes'
    )
    context = {
        **summary,
        **_get_character_card_context(request.user),
        'balance_display':  format_minutes_display(summary['balance']),
        'budget_display':   format_minutes_display(summary['budget']),
        'spent_display':    format_minutes_display(summary['spent']),
        'earned_display':   format_minutes_display(summary['earned']),
        'remaining_display': format_minutes_display(summary['balance']),
        'budget_available_display': format_minutes_display(summary['budget'] + summary['earned']),
        'today_records': records,
        'today_record_count': get_today_record_count(request.user),
        'active_tab': 'home',
        'credit_grade': request.user.credit_grade,
        'grade_name': request.user.grade_name,
        'streak_days': request.user.streak_days,
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
        get_today_home_summary(user), mode='minutes',
    )

    context = {
        **summary,
        **_get_character_card_context(user),  # 캐릭터 카드용 값들 (main_progress와 동일)
        'balance_display':  format_unit_display(summary['spent'], base, unit),
        'budget_display':   format_minutes_display(summary['budget']),
        'spent_display':    format_minutes_display(summary['spent']),
        'earned_display':   format_minutes_display(summary['earned']),
        'remaining_display': format_minutes_display(summary['balance']),
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
        'bonus_rate_percent': int(
            get_exchange_bonus_rate(request.user.credit_grade) * 100
        ),
    }
    return render(request, 'ledger/main_convert.html', context)

@login_required
def record_history(request):
    """전체 기록 화면 - 선택한 날짜의 지출/수입 기록을 캘린더 형식으로 보여줌."""
    import datetime as dt
    
    def _format_md(d):
            # "8월 15일" 포맷. strftime('%-m월 %-d일')은 macOS/Linux 전용이라
            # Windows 팀원 환경에서도 동일하게 동작하도록 직접 조합함.
            return f"{d.month}월 {d.day}일"
        
    # 선택된 날짜 (쿼리스트링 ?date=YYYY-MM-DD, 없으면 오늘)
    date_str = request.GET.get('date')
    if date_str:
        try:
            selected_date = dt.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = get_today_kst()
    else:
        selected_date = get_today_kst()

    filter_type = request.GET.get('filter', 'all')  # all | earn | spend

    # 선택된 날짜가 속한 주(월~일) 계산 - get_week_range가 '월요일 00:00 ~ 다음주 월요일 00:00'을
    # 반환하므로 그 시작일 기준으로 7일치 날짜 리스트를 만듦
    week_start, _ = get_week_range(
        dt.datetime.combine(selected_date, dt.time.min, tzinfo=KST)
    )
    WEEKDAY_LABELS = ['월', '화', '수', '목', '금', '토', '일']
    week_days = [
        {
            'date': week_start.date() + dt.timedelta(days=i),
            'label': WEEKDAY_LABELS[i],
        }
        for i in range(7)
    ]
    for d in week_days:
        d['is_selected'] = d['date'] == selected_date

    # 해당 날짜의 기록 조회
    earn_qs = EarnRecord.objects.filter(
        users=request.user, earn_date=selected_date
    ).select_related('activity').order_by('-earn_start')
    spend_qs = SpendRecord.objects.filter(
        users=request.user, spend_date=selected_date
    ).order_by('-spend_start')

    earn_total = earn_qs.aggregate(total=Sum('earn_min'))['total'] or Decimal('0')
    spend_total = Decimal(spend_qs.aggregate(total=Sum('duration_min'))['total'] or 0)
    today_balance = earn_total - spend_total

    # TODO: verify_method 실제 저장값이 영문('timer'/'manual')인지 한글인지 확인 필요.
    # 확인되면 이 매핑에서 안 쓰는 쪽 지우면 됨.
    EARN_METHOD_DISPLAY = {
        'timer': '타이머', 'manual': '수동 입력',
        '타이머': '타이머', '수동': '수동 입력',
    }

    items = []
    for e in earn_qs:
        local_time = timezone.localtime(e.created_at)
        items.append({
            'type': 'earn',
            'label': e.activity.activity_type,
            'icon': EARN_ACTIVITY_ICONS.get(e.activity.activity_type, DEFAULT_EARN_ICON),
            'time_display': local_time.strftime('%p %I:%M').replace('AM', '오전').replace('PM', '오후'),
            'method_display': EARN_METHOD_DISPLAY.get(e.verify_method, e.verify_method),
            'value_display': f"+{format_minutes_display(e.earn_min)}",
            'is_positive': True,
        })
    for s in spend_qs:
        local_time = timezone.localtime(s.created_at)
        items.append({
            'type': 'spend',
            'label': get_category_display(s.category),
            'icon': SPEND_CATEGORY_ICONS.get(s.category, DEFAULT_ICON),
            'time_display': local_time.strftime('%p %I:%M').replace('AM', '오전').replace('PM', '오후'),
            # SpendRecord엔 기록 방식 필드가 없어서 method_display 없음 (TODO: 필드 생기면 채우기)
            'method_display': None,
            'value_display': f"-{format_minutes_display(s.duration_min)}",
            'is_positive': False,
        })

    earn_count = len(items) and sum(1 for i in items if i['type'] == 'earn')
    spend_count = len(items) and sum(1 for i in items if i['type'] == 'spend')

    if filter_type == 'earn':
        items = [i for i in items if i['type'] == 'earn']
    elif filter_type == 'spend':
        items = [i for i in items if i['type'] == 'spend']

    context = {
        'active_tab': 'home',
        'week_days': week_days,
        'selected_date': selected_date,
        'week_label': f"{_format_md(week_start.date())} - {_format_md(week_start.date() + dt.timedelta(days=6))}",
        'prev_week_date': (week_start.date() - dt.timedelta(days=7)).isoformat(),
        'next_week_date': (week_start.date() + dt.timedelta(days=7)).isoformat(),
        'selected_date_label': _format_md(selected_date),        'earn_total_display': f"+{format_minutes_display(earn_total)}",
        'spend_total_display': f"-{format_minutes_display(spend_total)}",
        'today_balance_display': (
            f"+{format_minutes_display(today_balance)}" if today_balance >= 0
            else format_minutes_display(today_balance)
        ),
        'is_balance_negative': today_balance < 0,
        'filter_type': filter_type,
        'total_count': earn_count + spend_count,
        'earn_count': earn_count,
        'spend_count': spend_count,
        'items': items,
    }
    return render(request, 'ledger/record_history.html', context)
@login_required
def league_journey(request):
    """리그 여정(로드맵) 화면 뷰"""
    journey_data = get_league_journey_data(request.user)

    context = {
        **journey_data,
        'closure_character_url': request.user.closure_character_url,
        'active_tab': 'home', #'deadline'였던 것 -> 홈에서 들어오는 화면이랑 'home'으로 바꾸긴 한데 논의 필요
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