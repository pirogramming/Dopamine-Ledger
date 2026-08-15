from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import Users
from accounts.kakao import send_kakao_memo
from ledger.models import DailyClose


class Command(BaseCommand):
    help = '23시 최종 마감 알림 발송'

    def handle(self, *args, **options):
        users = Users.objects.exclude(kakao_access_token__isnull=True)\
                             .exclude(kakao_access_token='')

        sent, skipped = 0, 0
        for user in users:
            if self._already_closed_today(user):
                skipped += 1
                continue

            text = (
                f"⏰ {user.nickname}님, 곧 오늘이 끝나요!\n"
                f"마감하지 않으면 연속 기록이 끊길 수 있어요. 지금 마감하세요!"
            )
            if send_kakao_memo(user, text):
                sent += 1
            else:
                self.stdout.write(f"발송 실패: {user.email}")

        self.stdout.write(self.style.SUCCESS(f'최종 알림 발송 {sent}건, 스킵 {skipped}건'))

    def _already_closed_today(self, user):
        return DailyClose.objects.filter(
            users=user, close_date=timezone.localdate()
        ).exists()