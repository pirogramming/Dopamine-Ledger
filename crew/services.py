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

# 마일스톤 기준 (연속 마감일 → 문구). 신용등급 배지와 동일 기준
CLOSE_MILESTONES = {
    3:  '브론즈',
    7:  '실버',
    14: '골드',
    21: '플래티넘',
}

def create_close_feed(user, streak_days):
    """하루 마감 시 유저가 속한 모든 크루에 피드 생성.
    - 기본: '오늘 마감했어요'
    - 마일스톤(3·7·14·21일) 달성일이면 특별 피드 추가."""
    from crew.models import CrewMember, FeedEvent

    crew_ids = list(
        CrewMember.objects.filter(users=user).values_list('crew_id', flat=True)
    )
    if not crew_ids:
        return

    # 기본 마감 피드
    base_events = [
        FeedEvent(
            crew_id=cid,
            actor=user,
            event_type=FeedEvent.EventType.CLOSE,
            message=f'{user}님이 오늘 하루를 마감했어요 (연속 {streak_days}일째)',
        )
        for cid in crew_ids
    ]

    # 마일스톤 달성일이면 추가 피드
    milestone = CLOSE_MILESTONES.get(streak_days)
    if milestone:
        base_events += [
            FeedEvent(
                crew_id=cid,
                actor=user,
                event_type=FeedEvent.EventType.CLOSE,
                message=f'🎉 {user}님이 {streak_days}일 연속 마감으로 {milestone} 등급을 달성했어요!',
            )
            for cid in crew_ids
        ]

    FeedEvent.objects.bulk_create(base_events)   # 쿼리 1번

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