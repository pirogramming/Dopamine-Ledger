from decimal import Decimal

from django.test import SimpleTestCase

from .services import calculate_earn_minutes


class CalculateEarnMinutesTest(SimpleTestCase):

    def test_calculate_earn_minutes(self):
        result = calculate_earn_minutes(
            30,
            Decimal("0.50"),
        )

        self.assertEqual(result, Decimal("15.00"))

    def test_invalid_duration(self):
        with self.assertRaises(ValueError):
            calculate_earn_minutes(
                0,
                Decimal("0.50"),
            )

    def test_invalid_rate(self):
        with self.assertRaises(ValueError):
            calculate_earn_minutes(
                30,
                Decimal("1.00"),
            )