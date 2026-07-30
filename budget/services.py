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