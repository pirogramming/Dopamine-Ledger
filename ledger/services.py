from datetime import datetime, time, timedelta
from django.db.models import Sum
from django.utils import timezone
import zoneinfo

KST = zoneinfo.ZoneInfo("Asia/Seoul")


def get_week_range(reference_dt=None):
    """이번 주 (월요일 00:00, 다음 주 월요일 00:00) — Asia/Seoul.
    잔액·마감·결산이 전부 이 함수를 임포트해서 같은 경계를 써야 함."""
    if reference_dt is None:
        reference_dt = timezone.now()
    local = reference_dt.astimezone(KST)
    monday_date = (local - timedelta(days=local.weekday())).date()
    start = datetime.combine(monday_date, time.min, tzinfo=KST)
    end = start + timedelta(days=7)
    return start, end


def get_current_balance(user, reference_dt=None):
    """이번 주 잔액 = weekly_budget_min + Σearn_min - Σduration_min.
    음수 허용. 저장 안 함 — 매번 집계."""
    # 순환 임포트 방지 위해 함수 안에서 임포트
    from ledger.models import EarnRecord, SpendRecord

    start, end = get_week_range(reference_dt)
    start_date, end_date = start.date(), end.date()

    earned = EarnRecord.objects.filter(
        users=user,
        earn_date__gte=start_date,
        earn_date__lt=end_date,
    ).aggregate(total=Sum('earn_min'))['total'] or Decimal('0')

    spent_min = SpendRecord.objects.filter(
        users=user,
        spend_date__gte=start_date,
        spend_date__lt=end_date,
    ).aggregate(total=Sum('duration_min'))['total'] or 0

    return user.weekly_budget_min + earned - Decimal(spent_min)


def get_week_summary(user, reference_dt=None):
    """홈 화면용: 잔액 + 게이지 계산에 필요한 값들 한 번에."""
    from ledger.models import EarnRecord, SpendRecord

    start, end = get_week_range(reference_dt)
    start_date, end_date = start.date(), end.date()

    earned = EarnRecord.objects.filter(
        users=user, earn_date__gte=start_date, earn_date__lt=end_date,
    ).aggregate(total=Sum('earn_min'))['total'] or Decimal('0')

    spent = SpendRecord.objects.filter(
        users=user, spend_date__gte=start_date, spend_date__lt=end_date,
    ).aggregate(total=Sum('duration_min'))['total'] or 0
    spent = Decimal(spent)

    budget = user.weekly_budget_min
    balance = budget + earned - spent
    total_available = budget + earned  # 게이지 분모
    percent_used = (
        min(int((spent / total_available) * 100), 999)
        if total_available > 0 else 0
    )

    return {
        'balance': balance,
        'budget': budget,
        'earned': earned,
        'spent': spent,
        'percent_used': percent_used,
        'is_overspent': balance < 0,
    }