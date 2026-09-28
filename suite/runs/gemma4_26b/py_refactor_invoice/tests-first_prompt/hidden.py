import sys
sys.path.insert(0, ".")
def check(name, fn):
    try:
        ok = bool(fn())
    except BaseException:
        ok = False
    print(("PASS " if ok else "FAIL ") + name, flush=True)
def raises(exc, fn):
    try:
        fn()
    except exc:
        return True
    except BaseException:
        return False
    return False
import solution as S

I = [{"price": 100, "qty": 2}]
check("US no coupon", lambda: S.calc(I) == 216.0)
check("SAVE10 taxed after discount", lambda: S.calc(I, "SAVE10") == 194.4)
check("PK SAVE10", lambda: S.calc(I, "SAVE10", "PK") == 210.6)
check("FLAT5 US", lambda: S.calc(I, "FLAT5", "US") == 210.6)
check("FLAT5 floors at 0", lambda: S.calc([{"price": 3, "qty": 1}], "FLAT5", "PK") == 0.0)
check("unknown country no tax", lambda: S.calc(I, None, "DE") == 200.0)
check("qty <= 0 ignored", lambda: S.calc([{"price": 50, "qty": 0}, {"price": 10, "qty": -2}, {"price": 1, "qty": 1}], None, "DE") == 1.0)
check("unknown coupon ValueError", lambda: raises(ValueError, lambda: S.calc(I, "BOGUS")))
check("empty string coupon = none", lambda: S.calc(I, "") == 216.0)
check("half-up rounding (0.125 -> 0.13)", lambda: S.calc([{"price": 0.125, "qty": 1}], None, "DE") == 0.13)
check("no float drift", lambda: S.calc([{"price": 0.1, "qty": 3}], None, "US") == 0.32)
check("returns float", lambda: isinstance(S.calc(I), float))
check("empty items", lambda: S.calc([]) == 0.0)
