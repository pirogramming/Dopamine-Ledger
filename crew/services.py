# crew/services.py
from .models import CrewMember, FeedEvent


def create_earn_feed(user, activity_name, earned_min):
    """
    유저가 활동으로 벌었을 때, 그가 속한 모든 크루에 피드 이벤트 생성.
    ledger의 EarnRecord 저장 직후 호출한다.
    """
    earned = int(round(earned_min or 0))
    if earned <= 0:
        return

    message = f"{user}님이 {activity_name} {earned}분 벌이"

    memberships = CrewMember.objects.filter(users=user).select_related('crew')
    events = [
        FeedEvent(
            crew=m.crew,
            actor=user,
            event_type=FeedEvent.EventType.EARN,
            message=message,
        )
        for m in memberships
    ]
    FeedEvent.objects.bulk_create(events)

def create_overspend_feed(user, overspend_min):
    """
    과예산 지출(예산 넘긴 부분)이 발생하면, 유저가 속한 모든 크루에 SPEND 피드 생성.
    ledger의 SpendRecord 저장 직후, 과예산분이 있을 때만 호출.
    """
    overspend_min = int(round(overspend_min or 0))
    if overspend_min <= 0:
        return

    message = f"{user}님이 예산을 {overspend_min}분 초과했어요"

    memberships = CrewMember.objects.filter(users=user).select_related('crew')
    events = [
        FeedEvent(
            crew=m.crew,
            actor=user,
            event_type=FeedEvent.EventType.SPEND,
            message=message,
        )
        for m in memberships
    ]
    FeedEvent.objects.bulk_create(events)