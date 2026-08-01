from decimal import Decimal

from django.test import SimpleTestCase

from .services import calculate_earn_minutes, convert_earn_to_unit


class CalculateEarnMinutesTest(SimpleTestCase):

    def test_calculate_earn_minutes(self):
        result = calculate_earn_minutes(
            30,
            Decimal("0.50"),
        )

        self.assertEqual(result, Decimal("15.00"))

    def test_small_positive_rate(self):
        result = calculate_earn_minutes(
            100,
            Decimal("0.005"),
        )

        self.assertEqual(result, Decimal("0.50"))

    def test_maximum_rate(self):
        result = calculate_earn_minutes(
            100,
            Decimal("0.99"),
        )

        self.assertEqual(result, Decimal("99.00"))

    def test_invalid_duration(self):
        with self.assertRaises(ValueError):
            calculate_earn_minutes(
                0,
                Decimal("0.50"),
            )

    def test_rate_zero(self):
        with self.assertRaises(ValueError):
            calculate_earn_minutes(
                30,
                Decimal("0"),
            )

    def test_rate_one(self):
        with self.assertRaises(ValueError):
            calculate_earn_minutes(
                30,
                Decimal("1.00"),
            )


class ConvertEarnToUnitTest(SimpleTestCase):

    def test_convert_earn_to_unit(self):
        result = convert_earn_to_unit(
            Decimal("30"),
            Decimal("20"),
        )

        self.assertEqual(result, Decimal("1.50"))

    def test_zero_earn_amount(self):
        result = convert_earn_to_unit(
            Decimal("0"),
            Decimal("20"),
        )

        self.assertEqual(result, Decimal("0.00"))

    def test_round_half_up(self):
        result = convert_earn_to_unit(
            Decimal("1"),
            Decimal("6"),
        )

        self.assertEqual(result, Decimal("0.17"))

    def test_invalid_earn_amount(self):
        with self.assertRaises(ValueError):
            convert_earn_to_unit(
                Decimal("-1"),
                Decimal("20"),
            )

    def test_invalid_conversion_rate(self):
        with self.assertRaises(ValueError):
            convert_earn_to_unit(
                Decimal("30"),
                Decimal("0"),
            )