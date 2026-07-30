from decimal import Decimal, ROUND_HALF_UP


def calculate_earn_minutes(duration_min, rate):
    duration_min = Decimal(str(duration_min))
    rate = Decimal(str(rate))

    if duration_min <= 0:
        raise ValueError("duration_min must be greater than 0")

    if rate < Decimal("0.01") or rate >= Decimal("1.00"):
        raise ValueError("rate must be between 0.01 and 0.99")

    raw_earn_min = duration_min * rate

    return raw_earn_min.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def convert_earn_to_unit(earn_amount, conversion_rate):
    earn_amount = Decimal(str(earn_amount))
    conversion_rate = Decimal(str(conversion_rate))

    if earn_amount < 0:
        raise ValueError("earn_amount must be greater than or equal to 0")

    if conversion_rate <= 0:
        raise ValueError("conversion_rate must be greater than 0")

    converted_unit = earn_amount / conversion_rate

    return converted_unit.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )