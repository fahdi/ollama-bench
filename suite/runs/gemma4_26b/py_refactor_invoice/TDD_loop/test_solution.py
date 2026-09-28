import unittest
from solution import calc

class TestCalc(unittest.TestCase):
    # --- Normal Cases ---
    def test_basic_calculation(self):
        # (10 * 2) = 20. Tax US (8%) = 1.6. Total = 21.6
        items = [{"price": 10.0, "qty": 2}]
        self.assertEqual(calc(items, country="US"), 21.6)

    def test_multiple_items(self):
        # (10*2) + (5*1) = 25. Tax PK (17%) = 4.25. Total = 29.25
        items = [{"price": 10.0, "qty": 2}, {"price": 5.0, "qty": 1}]
        self.assertEqual(calc(items, country="PK"), 29.25)

    def test_ignore_zero_or_negative_qty(self):
        items = [{"price": 10.0, "qty": 2}, {"price": 5.0, "qty": 0}, {"price": 5.0, "qty": -1}]
        # Only 20.0 counts. Tax US (8%) = 1.6. Total = 21.6
        self.assertEqual(calc(items, country="US"), 21.6)

    # --- Bug Fix 1: Tax on Discounted Subtotal ---
    def test_tax_computed_after_discount(self):
        # Subtotal: 100. 
        # SAVE10: 100 - 10% = 90.
        # Tax (US 8% of 90): 7.2.
        # Total: 97.2
        items = [{"price": 100.0, "qty": 1}]
        self.assertEqual(calc(items, coupon="SAVE10", country="US"), 97.2)

        # Subtotal: 100.
        # FLAT5: 100 - 5 = 95.
        # Tax (US 8% of 95): 7.6.
        # Total: 102.6
        self.assertEqual(calc(items, coupon="FLAT5", country="US"), 102.6)

    # --- Bug Fix 2: FLAT5 Floor at 0 ---
    def test_flat5_floor_at_zero(self):
        # Subtotal: 3. FLAT5 makes it -2, but must floor at 0.
        # Tax (US 8% of 0): 0. Total: 0.0
        items = [{"price": 3.0, "qty": 1}]
        self.assertEqual(calc(items, coupon="FLAT5", country="US"), 0.0)

    # --- Coupon Logic & Errors ---
    def test_no_coupon(self):
        items = [{"price": 10.0, "qty": 1}]
        self.assertEqual(calc(items, coupon=None, country="US"), 10.8)
        self.assertEqual(calc(items, coupon="", country="US"), 10.8)

    def test_invalid_coupon_raises_error(self):
        items = [{"price": 10.0, "qty": 1}]
        with self.assertRaises(ValueError):
            calc(items, coupon="INVALID_CODE")

    # --- Country Logic ---
    def test_unknown_country_no_tax(self):
        items = [{"price": 100.0, "qty": 1}]
        # Subtotal 100. Tax 0. Total 100.
        self.assertEqual(calc(items, country="FR"), 100.0)

    # --- Precision & Rounding ---
    def test_decimal_precision_and_rounding(self):
        # Testing "Round Half Up" behavior
        # Subtotal: 10.05. No discount. No tax.
        # If we round 10.05 to 2 places, it's 10.05.
        # Let's try a case that forces a rounding decision:
        # Subtotal: 10.045 (if it were possible via math)
        # Using items that result in 10.045:
        # 10.045 * 1 (no tax) -> should round to 10.05
        items = [{"price": 10.045, "qty": 1}]
        self.assertEqual(calc(items), 10.05)

        # 10.044 -> 10.04
        items = [{"price": 10.044, "qty": 1}]
        self.assertEqual(calc(items), 10.04)

if __name__ == "__main__":
    unittest.main()
