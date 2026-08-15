import random
import string

from django.conf import settings
from django.db import models


def generate_invite_code(length=6):
    """중복되지 않는 초대 코드 생성 (대문자 + 숫자)"""
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choices(chars, k=length))
        if not Crew.objects.filter(invite_code=code).exists():
            return code


class Crew(models.Model):
    class Status(models.TextChoices):
        WAITING = 'WAITING', '대기중'
        ACTIVE = 'ACTIVE', '활성'

    MAX_MEMBERS = 6          # 최대 정원
    ACTIVATE_THRESHOLD = 3   # 이 인원 이상이면 활성 전환

    name = models.CharField('크루명', max_length=50)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='owned_crews',
        verbose_name='크루장',
    )
    invite_code = models.CharField('초대 코드', max_length=10, unique=True)
    status = models.CharField(
        '상태', max_length=10,
        choices=Status.choices, default=Status.WAITING,
    )

    class Meta:
        db_table = 'crew'

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        return self.members.count()

    @property
    def is_full(self):
        return self.member_count >= self.MAX_MEMBERS

    def refresh_status(self):
        """멤버 수에 따라 상태를 갱신한다 (3명 이상 → 활성)."""
        if self.member_count >= self.ACTIVATE_THRESHOLD and self.status != self.Status.ACTIVE:
            self.status = self.Status.ACTIVE
            self.save(update_fields=['status'])

class CrewMember(models.Model):
    crew = models.ForeignKey(
        Crew, on_delete=models.CASCADE, related_name='members'
    )
    users = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='crew_memberships'
    )
    joined_date = models.DateField('가입일', auto_now_add=True)
    
    @property
    def profile_character_url(self) -> str:
        """연결된 User 객체의 프로필 두상 캐릭터 URL을 가져옴"""
        return self.users.profile_character_url

    class Meta:
        db_table = 'crew_member'
        unique_together = [['crew', 'users']]

class CrewGoal(models.Model):
    crew = models.OneToOneField(
        Crew, on_delete=models.CASCADE, related_name='goal'
    )
    target_minutes = models.PositiveIntegerField('목표 시간(분)', default=1200)  # 기본 20시간
    reward_text = models.CharField('보상 문구', max_length=100, blank=True)

    class Meta:
        db_table = 'crew_goal'

    def __str__(self):
        return f'{self.crew.name} 목표'

    @property
    def target_hours(self):
        """목표 시간을 '시간' 단위로 (화면 표시용)"""
        return self.target_minutes // 60

class FeedEvent(models.Model):
    class EventType(models.TextChoices):
        EARN  = 'earn',  '벌이'
        SPEND = 'spend', '과예산 지출'
        CHEER = 'cheer', '응원'
        CLOSE = 'close', '마감'
        LEAVE = 'leave', '탈퇴'
        KICK  = 'kick',  '내보내기'

    crew = models.ForeignKey(
        Crew, on_delete=models.CASCADE, related_name='feed_events'
    )
    # 이벤트를 일으킨 사람 (벌이한 사람, 응원 보낸 사람)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='feed_events'
    )
    # 대상이 있는 경우만 (응원 받은 사람). 나머진 null
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='feed_events_received',
        null=True, blank=True,
    )
    event_type = models.CharField(max_length=10, choices=EventType.choices)
    message = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'feed_event'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['crew', '-created_at'])]

    def __str__(self):
        return f'[{self.crew.name}] {self.get_event_type_display()} - {self.message}'