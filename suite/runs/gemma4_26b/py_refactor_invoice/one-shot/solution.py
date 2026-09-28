from decimal import Decimal, ROUND_HALF_UP

def calc(items, coupon=None, country="US"):
    """
    Calculates the total price for a list of items, applying discounts and taxes.
    
    Fixes:
    1. Tax is calculated on the discounted subtotal.
    2. FLAT5 discount is floored at 0 to prevent negative subtotals.
    3. Unknown coupons raise ValueError.
    4. Uses Decimal for exact arithmetic to avoid float drift.
    """
    
    # 1. Calculate initial subtotal
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
        discounted_subtotal = subtotal
    elif effective_coupon == "SAVE10":
        discounted_subtotal = subtotal * Decimal("0.90")
    elif effective_coupon == "FLAT5":
        discounted_subtotal = max(Decimal("0.00"), subtotal - Decimal("5.00"))
    else:
        # Unknown coupon code
        raise ValueError(f"Unknown coupon code: {coupon}")

    # 3. Calculate Tax based on the DISCOUNTED subtotal
    tax_rates = {
        "US": Decimal("0.08"),
        "PK": Decimal("0.17")
    }
    tax_rate = tax_rates.get(country, Decimal("0.00"))
    tax_amount = discounted_subtotal * tax_rate

    # 4. Final Total
    total = discounted_subtotal + tax_amount

    # Round to 2 decimal places using ROUND_HALF_UP and return as float
    return float(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
