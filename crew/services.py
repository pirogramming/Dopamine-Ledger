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