from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import Users
from accounts.kakao import send_kakao_memo
from ledger.models import DailyClose

# 배포 시 EC2 crontab 등록 필요:
# 0 12 * * * (UTC 12시 = KST 21시) docker compose exec -T web python manage.py send_close_reminder
class Command(BaseCommand):
    help = '오늘 마감 안 한 카카오 연결 유저에게 마감 알림 발송'

    def handle(self, *args, **options):
        users = Users.objects.exclude(kakao_access_token__isnull=True)\
                             .exclude(kakao_access_token='')

        sent, skipped = 0, 0
        for user in users:
            if self._already_closed_today(user):
                skipped += 1
                continue

            text = (
                f"🌙 {user.nickname}님, 오늘 하루 마감하셨나요?\n"
                f"마감하고 연속 기록을 이어가세요!"
            )
            if send_kakao_memo(user, text):
                sent += 1
            else:
                self.stdout.write(f"발송 실패: {user.email}")

        self.stdout.write(self.style.SUCCESS(f'발송 {sent}건, 스킵 {skipped}건'))

    def _already_closed_today(self, user):
        return DailyClose.objects.filter(
            users=user, close_date=timezone.localdate()
        ).exists()