from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import DailyClose
from .services import close_today, get_today_record_summary


User = get_user_model()


class DailyCloseServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="daily-close-test",
            email="daily-close@example.com",
            password="test-password-1234",
            nickname="마감테스트",
        )
        self.today = timezone.localdate()

    def get_summary_with_record(self):
        """
        오늘 기록이 1건 이상 존재하는 상황을 가정한 summary.
        """
        return {
            "today": self.today,
            "today_earn": 0,
            "today_spend": 10,
            "has_earn_record": False,
            "has_spend_record": True,
        }

    def test_summary_without_records(self):
        summary = get_today_record_summary(self.user)

        self.assertEqual(summary["today"], self.today)
        self.assertEqual(summary["today_earn"], 0)
        self.assertEqual(summary["today_spend"], 0)
        self.assertFalse(summary["has_earn_record"])
        self.assertFalse(summary["has_spend_record"])

    def test_close_without_records_raises_error(self):
        with self.assertRaisesMessage(
            ValueError,
            "오늘 기록이 없습니다.",
        ):
            close_today(self.user)

        self.assertFalse(
            DailyClose.objects.filter(
                users=self.user,
                close_date=self.today,
            ).exists()
        )

    @patch("ledger.services.get_today_record_summary")
    def test_close_with_record(self, mock_summary):
        mock_summary.return_value = self.get_summary_with_record()

        daily_close = close_today(self.user)

        self.user.refresh_from_db()

        self.assertEqual(daily_close.users, self.user)
        self.assertEqual(daily_close.close_date, self.today)
        self.assertEqual(self.user.streak_days, 1)

    @patch("ledger.services.get_today_record_summary")
    def test_close_twice_raises_error(self, mock_summary):
        mock_summary.return_value = self.get_summary_with_record()

        close_today(self.user)

        with self.assertRaisesMessage(
            ValueError,
            "오늘은 이미 마감했습니다.",
        ):
            close_today(self.user)

        self.assertEqual(
            DailyClose.objects.filter(
                users=self.user,
                close_date=self.today,
            ).count(),
            1,
        )

    @patch("ledger.services.get_today_record_summary")
    def test_streak_increases_when_yesterday_was_closed(
        self,
        mock_summary,
    ):
        mock_summary.return_value = self.get_summary_with_record()

        DailyClose.objects.create(
            users=self.user,
            close_date=self.today - timedelta(days=1),
            closed_at=timezone.now() - timedelta(days=1),
        )

        self.user.streak_days = 3
        self.user.save(update_fields=["streak_days"])

        close_today(self.user)

        self.user.refresh_from_db()

        self.assertEqual(self.user.streak_days, 4)

    @patch("ledger.services.get_today_record_summary")
    def test_streak_restarts_when_previous_close_is_not_yesterday(
        self,
        mock_summary,
    ):
        mock_summary.return_value = self.get_summary_with_record()

        DailyClose.objects.create(
            users=self.user,
            close_date=self.today - timedelta(days=2),
            closed_at=timezone.now() - timedelta(days=2),
        )

        self.user.streak_days = 5
        self.user.save(update_fields=["streak_days"])

        close_today(self.user)

        self.user.refresh_from_db()

        self.assertEqual(self.user.streak_days, 1)