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
    """이번 주 범위: 월요일 00:00 ~ 다음 주 월요일 00:00, Asia/Seoul 기준"""
    if reference_dt is None:
        reference_dt = timezone.now()

    local = reference_dt.astimezone(KST)
    monday_date = (local - timedelta(days=local.weekday())).date()

    start = datetime.combine(
        monday_date,
        time.min,
        tzinfo=KST,
    )
    end = start + timedelta(days=7)

    return start, end


def get_current_balance(user, reference_dt=None):
    """이번 주 잔액 = 주간 예산 + 수입 합계 - 지출 합계"""
    from ledger.models import EarnRecord, SpendRecord

    start, end = get_week_range(reference_dt)
    start_date = start.date()
    end_date = end.date()

    earned = EarnRecord.objects.filter(
        users=user,
        earn_date__gte=start_date,
        earn_date__lt=end_date,
    ).aggregate(
        total=Sum("earn_min")
    )["total"] or Decimal("0")

    spent_min = SpendRecord.objects.filter(
        users=user,
        spend_date__gte=start_date,
        spend_date__lt=end_date,
    ).aggregate(
        total=Sum("duration_min")
    )["total"] or 0

    return (
        user.weekly_budget_min
        + earned
        - Decimal(spent_min)
    )