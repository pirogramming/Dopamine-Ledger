from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, time, timedelta

from django.db.models import Sum
from django.utils import timezone
import zoneinfo


KST = zoneinfo.ZoneInfo("Asia/Seoul")


def calculate_earn_minutes(duration_min, rate):
    duration_min = Decimal(str(duration_min))
    rate = Decimal(str(rate))

    if duration_min <= 0:
        raise ValueError("duration_min must be greater than 0")

    if rate <= Decimal("0") or rate >= Decimal("1.00"):
        raise ValueError(
            "rate must be between 0 (exclusive) and 1.0 (exclusive)"
        )

    raw_earn_min = duration_min * rate

    return raw_earn_min.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def convert_earn_to_unit(earn_minutes, conversion_rate):
    # conversion_rate = "1단위당 소요 분" (accounts.Users.conversion_base와 동일 의미)
    # 결과 = earn_minutes ÷ conversion_rate. 예: 180 ÷ 360(책1권=360분) = 0.5권
    earn_minutes = Decimal(str(earn_minutes))
    conversion_rate = Decimal(str(conversion_rate))

    if earn_minutes < 0:
        raise ValueError("earn_minutes must be greater than or equal to 0")

    if conversion_rate <= 0:
        raise ValueError("conversion_rate must be greater than 0")

    converted_unit = earn_minutes / conversion_rate

    return converted_unit.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )





def get_week_range(reference_dt=None):
    """이번 주 (월요일 00:00, 다음 주 월요일 00:00) — Asia/Seoul.
    잔액·마감·결산이 전부 이 함수를 임포트해서 같은 경계를 쓰게 함."""
    if reference_dt is None:
        reference_dt = timezone.now()
    local = reference_dt.astimezone(KST)
    monday_date = (local - timedelta(days=local.weekday())).date()
    start = datetime.combine(monday_date, time.min, tzinfo=KST)
    end = start + timedelta(days=7)
    return start, end


def get_today_kst():
    return timezone.now().astimezone(KST).date()


def get_current_balance(user, reference_dt=None):
    """이번 주 잔액 = weekly_budget_min + Σearn_min - Σduration_min.
    음수 허용. 저장 안 함 — 매번 집계."""
    from ledger.models import EarnRecord, SpendRecord

    start, end = get_week_range(reference_dt)
    start_date, end_date = start.date(), end.date()

    earned = EarnRecord.objects.filter(
        users=user,
        earn_date__gte=start_date, earn_date__lt=end_date,
    ).aggregate(total=Sum('earn_min'))['total'] or Decimal('0')

    spent_min = SpendRecord.objects.filter(
        users=user,
        spend_date__gte=start_date, spend_date__lt=end_date,
    ).aggregate(total=Sum('duration_min'))['total'] or 0

    return user.weekly_budget_min + earned - Decimal(spent_min)


def get_week_summary(user, reference_dt=None):
    """홈 화면 컨텍스트용. 표시 문자열은 view에서 별도 포맷."""
    from ledger.models import EarnRecord, SpendRecord

    start, end = get_week_range(reference_dt)
    start_date, end_date = start.date(), end.date()

    earned = EarnRecord.objects.filter(
        users=user, earn_date__gte=start_date, earn_date__lt=end_date,
    ).aggregate(total=Sum('earn_min'))['total'] or Decimal('0')

    spent = Decimal(
        SpendRecord.objects.filter(
            users=user, spend_date__gte=start_date, spend_date__lt=end_date,
        ).aggregate(total=Sum('duration_min'))['total'] or 0
    )

    budget = user.weekly_budget_min
    balance = budget + earned - spent
    total_available = budget + earned  # 게이지 분모: 이번 주에 쓸 수 있었던 총량
    percent = (
        int((spent / total_available) * 100) if total_available > 0 else 0
    )
    return {
        'balance': balance,
        'budget': budget,
        'earned': earned,
        'spent': spent,
        'percent_used': min(percent, 999),        # 표시용(초과 시 999까지)
        'percent_used_capped': min(percent, 100), # bar 너비용
        'is_overspent': balance < 0,
    }


 #def is_overspent(user, reference_dt=None):
 #  """지출 저장 직후 이걸로 판정해서 True면 크루 피드 이벤트 생성.
 #   강성훈이 지출 저장 로직에서 호출."""
 #   return get_current_balance(user, reference_dt) < 0

# ---------- 표시 헬퍼 ----------

def format_minutes_display(m):
    """정수 분 → '1시간 30분' / '-30분'. 부호 그대로."""
    m = int(round(m))
    sign = "-" if m < 0 else ""
    m = abs(m)
    h, r = divmod(m, 60)
    if h and r: return f"{sign}{h}시간 {r}분"
    if h:      return f"{sign}{h}시간"
    return f"{sign}{r}분"


def format_unit_display(minutes, conversion_base, unit_label):
    """분 → 환산 단위 (소수점 1자리). '3.8권' / '-0.5권'.
    base가 없거나 0 이하면 시간 표시로 폴백."""
    if not conversion_base or Decimal(str(conversion_base)) <= 0:
        return format_minutes_display(minutes)
    m = Decimal(str(minutes))
    sign = "-" if m < 0 else ""
    val = (abs(m) / Decimal(str(conversion_base))).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP,
    )
    return f"{sign}{val}{unit_label or ''}"


# ---------- 표시용 카테고리 매핑 ----------
# category에 실제 저장되는 영문 값 → 화면에 보여줄 한글 이름
CATEGORY_DISPLAY_NAMES = {
    'short_form': '숏폼',
    # 다른 카테고리 값이 더 있으면 여기에 추가해주세요.
}


def get_category_display(category):
    """매핑에 없는 값은 원래 값 그대로 반환(누락 방지용 안전장치)."""
    return CATEGORY_DISPLAY_NAMES.get(category, category)


# ---------- 표시용 아이콘 매핑 ----------
# 지출 카테고리(category 원본값) → 정적 파일 경로
SPEND_CATEGORY_ICONS = {
    'short_form': 'ledger/images/icon-shortform.svg',
}

# 적립 활동(activity.activity_type) → 정적 파일 경로
# 여기 등록된 활동은 전용 아이콘, 그 외(온보딩에서 사용자가 직접 추가한 활동)는 icon-plus로 표시
EARN_ACTIVITY_ICONS = {
    '독서': 'ledger/images/icon-reading.svg',
    '공부': 'ledger/images/icon-study.svg',
    '운동': 'ledger/images/icon-exercise.svg',
}

DEFAULT_ICON = 'ledger/images/icon-default.svg'          # 지출 카테고리 폴백
DEFAULT_EARN_ICON = 'ledger/images/icon-plus.svg'        # 온보딩 커스텀 활동용 폴백

# ---------- 오늘 기록 ----------

def get_today_records(user):
    """오늘의 지출·수입 기록을 시작 시각순 리스트로."""
    from ledger.models import EarnRecord, SpendRecord

    today = get_today_kst()
    earns = EarnRecord.objects.filter(
        users=user, earn_date=today
    ).select_related('activity')
    spends = SpendRecord.objects.filter(users=user, spend_date=today)

    records = []
    for e in earns:
        records.append({
            'label': e.activity.activity_type,
            'icon': EARN_ACTIVITY_ICONS.get(
                e.activity.activity_type, DEFAULT_EARN_ICON,   # ← DEFAULT_ICON에서 변경
            ),
            'signed_min': e.earn_min,
            'is_positive': True,
            'started_at': e.earn_start,
        })
    for s in spends:
        records.append({
            'label': get_category_display(s.category),
            'icon': SPEND_CATEGORY_ICONS.get(s.category, DEFAULT_ICON),
            'signed_min': Decimal(-s.duration_min),
            'is_positive': False,
            'started_at': s.spend_start,
        })
    records.sort(key=lambda r: r['started_at'])
    return records

def attach_value_displays(records, mode='minutes', conversion_base=None, unit_label=None):
    """records에 value_display 붙임. mode='minutes' | 'unit'."""
    for r in records:
        if mode == 'unit':
            val = format_unit_display(r['signed_min'], conversion_base, unit_label)
        else:
            val = format_minutes_display(r['signed_min'])
        if r['signed_min'] > 0 and not val.startswith('+'):
            val = '+' + val
        r['value_display'] = val
    return records

def get_today_activity_summary(user):
    """오늘의 활동별 총합 요약.
    사용자의 모든 지출 카테고리 & 적립 활동을 미리 다 포함하고,
    각각의 오늘 총 시간을 계산해서 반환. 기록 없는 활동은 0분으로 표시."""
    from ledger.models import EarnRecord, SpendRecord
    from budget.models import Activity  # 경로는 실제 위치에 맞게

    today = get_today_kst()

    # 오늘 카테고리별 지출 총합
    spend_totals = {
        row['category']: row['total']
        for row in SpendRecord.objects
            .filter(users=user, spend_date=today)
            .values('category')
            .annotate(total=Sum('duration_min'))
    }

    # 오늘 활동별 적립 총합
    earn_totals = {
        row['activity__activity_type']: row['total']
        for row in EarnRecord.objects
            .filter(users=user, earn_date=today)
            .values('activity__activity_type')
            .annotate(total=Sum('earn_min'))
    }

    records = []

    # 1) 지출 카테고리 — SPEND_CATEGORY_ICONS에 등록된 것 모두
    for category, icon_path in SPEND_CATEGORY_ICONS.items():
        total = spend_totals.get(category, 0) or 0
        records.append({
            'label': get_category_display(category),
            'icon': icon_path,
            'signed_min': Decimal(-total),   # 지출은 음수
            'is_positive': False,
            'has_record': total > 0,
        })

    # 2) 적립 활동 — 사용자에게 등록된 활동들
    activities = Activity.objects.filter(users=user, is_active=True)
    for activity in activities:
        activity_type = activity.activity_type
        total = earn_totals.get(activity_type, 0) or Decimal(0)
        records.append({
            'label': activity_type,
            'icon': EARN_ACTIVITY_ICONS.get(
                activity_type, DEFAULT_EARN_ICON,              # ← DEFAULT_ICON에서 변경
            ),
            'signed_min': Decimal(total),
            'is_positive': True,
            'has_record': Decimal(total) > 0,
        })
    return records


def get_today_record_count(user):
    """오늘 실제로 기록된 건 수 (활동별 합산과 별개로, 몇 번 기록했는지)."""
    from ledger.models import EarnRecord, SpendRecord
    today = get_today_kst()
    return (
        EarnRecord.objects.filter(users=user, earn_date=today).count()
        + SpendRecord.objects.filter(users=user, spend_date=today).count()
    )

def get_today_spent_minutes(user):
    """오늘 하루 지출 총합(분). convert 페이지의 진행률 설명용."""
    from ledger.models import SpendRecord
    today = get_today_kst()
    total = SpendRecord.objects.filter(
        users=user, spend_date=today,
    ).aggregate(total=Sum('duration_min'))['total'] or 0
    return Decimal(total)

def get_ro_particle(word):
    """단어 끝 글자의 받침 유무에 따라 '로' 또는 '으로' 반환.
    받침 없음 또는 ㄹ받침 → '로', 그 외 받침 → '으로'."""
    if not word:
        return '로'
    last_char = word[-1]
    code = ord(last_char) - 0xAC00
    if code < 0 or code > 11171:
        return '로'  # 한글 완성형 음절이 아니면 안전하게 기본값
    jong = code % 28   # 종성(받침) 인덱스: 0=받침없음, 8=ㄹ
    if jong in (0, 8):
        return '로'
    return '으로'