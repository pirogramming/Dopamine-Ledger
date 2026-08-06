from datetime import timedelta

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

    def test_summary_without_records(self):
        summary = get_today_record_summary(self.user)

        self.assertEqual(summary["today"], self.today)
        self.assertEqual(summary["today_earn"], 0)
        self.assertEqual(summary["today_spend"], 0)
        self.assertFalse(summary["has_earn_record"])
        self.assertFalse(summary["has_spend_record"])

    def test_close_without_records_raises_error(self):
        with self.assertRaises(ValueError):
            close_today(self.user)

        self.assertFalse(
            DailyClose.objects.filter(
                users=self.user,
                close_date=self.today,
            ).exists()
        )

    def test_close_without_records_when_no_spend_checked(self):
        daily_close = close_today(
            self.user,
            no_spend_checked=True,
        )

        self.user.refresh_from_db()

        self.assertEqual(daily_close.users, self.user)
        self.assertEqual(daily_close.close_date, self.today)
        self.assertEqual(self.user.streak_days, 1)

    def test_close_twice_raises_error(self):
        close_today(
            self.user,
            no_spend_checked=True,
        )

        with self.assertRaises(ValueError):
            close_today(
                self.user,
                no_spend_checked=True,
            )

        self.assertEqual(
            DailyClose.objects.filter(
                users=self.user,
                close_date=self.today,
            ).count(),
            1,
        )

    def test_streak_increases_when_yesterday_was_closed(self):
        DailyClose.objects.create(
            users=self.user,
            close_date=self.today - timedelta(days=1),
            closed_at=timezone.now() - timedelta(days=1),
        )
        self.user.streak_days = 3
        self.user.save(update_fields=["streak_days"])

        close_today(
            self.user,
            no_spend_checked=True,
        )

        self.user.refresh_from_db()

        self.assertEqual(self.user.streak_days, 4)

    def test_streak_restarts_when_previous_close_is_not_yesterday(self):
        DailyClose.objects.create(
            users=self.user,
            close_date=self.today - timedelta(days=2),
            closed_at=timezone.now() - timedelta(days=2),
        )
        self.user.streak_days = 5
        self.user.save(update_fields=["streak_days"])

        close_today(
            self.user,
            no_spend_checked=True,
        )

        self.user.refresh_from_db()

        self.assertEqual(self.user.streak_days, 1)