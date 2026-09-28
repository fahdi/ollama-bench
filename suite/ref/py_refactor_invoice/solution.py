from decimal import Decimal, ROUND_HALF_UP
TAX = {"US": Decimal("0.08"), "PK": Decimal("0.17")}
def calc(items, coupon=None, country="US"):
    sub = sum((Decimal(str(i["price"])) * i["qty"] for i in items if i["qty"] > 0), Decimal(0))
    if coupon in (None, ""): pass
    elif coupon == "SAVE10": sub -= sub * Decimal("0.10")
    elif coupon == "FLAT5": sub = max(Decimal(0), sub - 5)
    else: raise ValueError("unknown coupon")
    total = sub + sub * TAX.get(country, Decimal(0))
    return float(total.quantize(Decimal("0.01"), ROUND_HALF_UP))
