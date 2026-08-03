from decimal import Decimal, ROUND_HALF_UP


def calculate_earn_minutes(duration_min, rate):
    duration_min = Decimal(str(duration_min))
    rate = Decimal(str(rate))

    if duration_min <= 0:
        raise ValueError("duration_min must be greater than 0")

    if rate <= Decimal("0") or rate >= Decimal("1.00"):
        raise ValueError(
            "rate must be between 0 (exclusive) and 1.0 (exclusive)"
        )

    raw_earn_min = duration_min * rate

    return raw_earn_min.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def convert_earn_to_unit(earn_minutes, conversion_rate):
    # conversion_rate = "1단위당 소요 분" (accounts.Users.conversion_base와 동일 의미)
    # 결과 = earn_minutes ÷ conversion_rate. 예: 180 ÷ 360(책1권=360분) = 0.5권
    earn_minutes = Decimal(str(earn_minutes))
    conversion_rate = Decimal(str(conversion_rate))

    if earn_minutes < 0:
        raise ValueError("earn_minutes must be greater than or equal to 0")

    if conversion_rate <= 0:
        raise ValueError("conversion_rate must be greater than 0")

    converted_unit = earn_minutes / conversion_rate

    return converted_unit.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )