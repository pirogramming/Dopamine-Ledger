from datetime import timedelta

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import DailyClose, EarnRecord, SpendRecord


def get_today_record_summary(user):
    """
    사용자의 오늘 수입/지출 정보를 조회한다.
    """
    today = timezone.localdate()

    earn_records = EarnRecord.objects.filter(
        users=user,
        earn_date=today,
    )
    spend_records = SpendRecord.objects.filter(
        users=user,
        spend_date=today,
    )

    today_earn = (
        earn_records.aggregate(total=Sum("earn_min"))["total"]
        or 0
    )
    today_spend = (
        spend_records.aggregate(total=Sum("duration_min"))["total"]
        or 0
    )

    return {
        "today": today,
        "today_earn": today_earn,
        "today_spend": today_spend,
        "has_earn_record": earn_records.exists(),
        "has_spend_record": spend_records.exists(),
    }


def close_today(user, no_spend_checked=False):
    """
    하루 마감을 처리하고 연속 마감일을 갱신한다.
    """

    today = timezone.localdate()

    # 이미 마감했는지 확인
    if DailyClose.objects.filter(
        users=user,
        close_date=today,
    ).exists():
        raise ValueError("오늘은 이미 마감했습니다.")

    summary = get_today_record_summary(user)

    # 오늘 기록이 하나도 없는 경우
    has_any_record = (
        summary["has_earn_record"]
        or summary["has_spend_record"]
    )

    if not has_any_record and not no_spend_checked:
        raise ValueError(
            "오늘 기록이 없습니다. "
            "'오늘 숏폼을 보지 않았어요'를 체크해주세요."
        )

    yesterday = today - timedelta(days=1)

    previous_close = (
        DailyClose.objects.filter(
            users=user,
            close_date__lt=today,
        )
        .order_by("-close_date")
        .first()
    )

    with transaction.atomic():
        daily_close = DailyClose.objects.create(
            users=user,
            close_date=today,
            closed_at=timezone.now(),
        )

        if (
            previous_close
            and previous_close.close_date == yesterday
        ):
            user.streak_days += 1
        else:
            user.streak_days = 1

        user.save(update_fields=["streak_days"])

    return daily_close