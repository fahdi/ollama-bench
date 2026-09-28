import unittest
from decimal import Decimal
from solution import calc

class TestCalc(unittest.TestCase):

    def test_basic_calculation(self):
        # Subtotal: 10 * 2 = 20. Tax (US 8%): 1.6. Total: 21.6
        items = [{"price": 10.0, "qty": 2}]
        self.assertEqual(calc(items, country="US"), 21.6)

    def test_tax_on_discounted_subtotal(self):
        # Subtotal: 100. Coupon SAVE10: 90. Tax (US 8% of 90): 7.2. Total: 97.2
        # Old bug: Tax was 8.0, Total was 97.0
        items = [{"price": 100.0, "qty": 1}]
        self.assertEqual(calc(items, coupon="SAVE10", country="US"), 97.2)

    def test_flat5_floor_at_zero(self):
        # Subtotal: 3. Coupon FLAT5: 3 - 5 = -2 -> floor to 0. Tax: 0. Total: 0
        items = [{"price": 3.0, "qty": 1}]
        self.assertEqual(calc(items, coupon="FLAT5", country="US"), 0.0)

    def test_flat5_normal(self):
        # Subtotal: 10. Coupon FLAT5: 5. Tax (US 8% of 5): 0.4. Total: 5.4
        items = [{"price": 10.0, "qty": 1}]
        self.assertEqual(calc(items, coupon="FLAT5", country="US"), 5.4)

    def test_different_countries(self):
        items = [{"price": 100.0, "qty": 1}]
        # PK: 17% tax
        self.assertEqual(calc(items, country="PK"), 117.0)
        # Unknown: 0% tax
        self.assertEqual(calc(items, country="FR"), 100.0)

    def test_ignore_invalid_qty(self):
        items = [
            {"price": 10.0, "qty": 2},
            {"price": 50.0, "qty": 0},
            {"price": 50.0, "qty": -1}
        ]
        # Subtotal: 20. Tax (US 8%): 1.6. Total: 21.6
        self.assertEqual(calc(items, country="US"), 21.6)

    def test_invalid_coupon_raises_error(self):
        items = [{"price": 10.0, "qty": 1}]
        with self.assertRaises(ValueError):
            calc(items, coupon="INVALID_CODE")

    def test_none_or_empty_coupon(self):
        items = [{"price": 10.0, "qty": 1}]
        self.assertEqual(calc(items, coupon=None), 10.0)
        self.assertEqual(calc(items, coupon=""), 10.0)

    def test_decimal_precision_and_rounding(self):
        # Test rounding half up: 0.005 should become 0.01
        # Subtotal: 0.005. Tax (US 8%): 0.0004. Total: 0.0054. 
        # Let's use a more concrete case:
        # Subtotal: 1.045. Tax (US 8%): 0.0836. Total: 1.1286 -> 1.13
        items = [{"price": 1.045, "qty": 1}]
        # 1.045 * 1.08 = 1.1286. Round half up -> 1.13
        self.assertEqual(calc(items, country="US"), 1.13)

if __name__ == "__main__":
    unittest.main()
