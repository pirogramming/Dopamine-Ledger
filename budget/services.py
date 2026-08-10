from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, time, timedelta

from django.db.models import Sum
from django.utils import timezone
import zoneinfo


KST = zoneinfo.ZoneInfo("Asia/Seoul")

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
    m = int(m)
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
EARN_ACTIVITY_ICONS = {
    '독서': 'ledger/images/icon-reading.svg',
    '공부': 'ledger/images/icon-study.svg',
    '운동': 'ledger/images/icon-exercise.svg',
}

DEFAULT_ICON = 'ledger/images/icon-default.svg'  # 매핑에 없는 카테고리/활동용 안전장치


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
            'icon': EARN_ACTIVITY_ICONS.get(e.activity.activity_type, DEFAULT_ICON),
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