from decimal import Decimal, ROUND_HALF_UP


MONEY_QUANT = Decimal("0.01")
PCT_QUANT = Decimal("0.000001")


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def pct(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(PCT_QUANT, rounding=ROUND_HALF_UP)

