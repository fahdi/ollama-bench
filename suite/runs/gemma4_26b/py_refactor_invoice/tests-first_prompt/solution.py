from decimal import Decimal, ROUND_HALF_UP

def calc(items, coupon=None, country="US"):
    """
    Calculates the total price including discounts and taxes.
    
    Args:
        items (list): List of dicts with 'price' and 'qty'.
        coupon (str): Coupon code ('SAVE10', 'FLAT5', or None/'').
        country (str): Country code for tax calculation.
        
    Returns:
        float: The final total rounded to 2 decimal places.
    """
    # Tax rates mapping
    TAX_RATES = {
        "US": Decimal("0.08"),
        "PK": Decimal("0.17")
    }
    
    # Valid coupons
    VALID_COUPONS = {"SAVE10", "FLAT5", None, ""}
    
    # 1. Calculate Subtotal using Decimal for precision
    subtotal = Decimal("0.00")
    for item in items:
        qty = item.get("qty", 0)
        if qty > 0:
            price = Decimal(str(item["price"]))
            subtotal += price * Decimal(str(qty))

    # 2. Apply Coupon
    if coupon not in VALID_COUPONS:
        raise ValueError(f"Invalid coupon code: {coupon}")

    discounted_subtotal = subtotal
    if coupon == "SAVE10":
        discounted_subtotal = subtotal * Decimal("0.90")
    elif coupon == "FLAT5":
        discounted_subtotal = subtotal - Decimal("5.00")
    
    # Ensure subtotal never goes below zero
    if discounted_subtotal < 0:
        discounted_subtotal = Decimal("0.00")

    # 3. Calculate Tax on the DISCOUNTED subtotal
    tax_rate = TAX_RATES.get(country, Decimal("0.00"))
    tax_amount = discounted_subtotal * tax_rate

    # 4. Final Total
    total = discounted_subtotal + tax_amount

    # 5. Round half up to 2 decimal places and return as float
    rounded_total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(rounded_total)
