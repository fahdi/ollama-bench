from decimal import Decimal, ROUND_HALF_UP

def calc(items, coupon=None, country="US"):
    # 1. Calculate initial subtotal using Decimal for precision
    subtotal = Decimal("0.00")
    for item in items:
        qty = item.get("qty", 0)
        if qty > 0:
            price = Decimal(str(item["price"]))
            subtotal += price * Decimal(str(qty))

    # 2. Apply Coupon
    # Handle None or empty string as no coupon
    effective_coupon = coupon if coupon else ""
    
    if effective_coupon == "":
        pass
    elif effective_coupon == "SAVE10":
        subtotal -= subtotal * Decimal("0.10")
    elif effective_coupon == "FLAT5":
        subtotal -= Decimal("5.00")
        # Bug Fix 2: Floor subtotal at 0
        if subtotal < 0:
            subtotal = Decimal("0.00")
    else:
        # Unknown coupon code
        raise ValueError(f"Invalid coupon: {coupon}")

    # 3. Calculate Tax on the DISCOUNTED subtotal (Bug Fix 1)
    tax_rates = {
        "US": Decimal("0.08"),
        "PK": Decimal("0.17")
    }
    tax_rate = tax_rates.get(country, Decimal("0.00"))
    tax = subtotal * tax_rate

    # 4. Final Total
    total = subtotal + tax

    # 5. Round ONLY the final total to 2 places, rounding half up
    # We convert to float at the very end as requested
    rounded_total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(rounded_total)
