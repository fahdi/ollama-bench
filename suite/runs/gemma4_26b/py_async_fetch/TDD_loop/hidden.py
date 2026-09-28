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

import asyncio
def run(c): return asyncio.run(c)
class T:
    def __init__(s): s.cur = 0; s.max = 0; s.calls = {}
    async def fetch(s, u):
        s.calls[u] = s.calls.get(u, 0) + 1
        s.cur += 1; s.max = max(s.max, s.cur)
        try:
            await asyncio.sleep(0.005 * (int(u[1:]) % 4 + 1) if u[1:].isdigit() else 0.005)
            return u.upper()
        finally:
            s.cur -= 1
URLS = [f"u{i}" for i in range(12)]
def order():
    t = T(); return run(S.fetch_all(URLS, t.fetch, limit=3)) == [u.upper() for u in URLS]
def limit3():
    t = T(); run(S.fetch_all(URLS, t.fetch, limit=3)); return t.max == 3
def limit1():
    t = T(); run(S.fetch_all(URLS[:5], t.fetch, limit=1)); return t.max == 1
def retry_ok():
    n = {"c": 0}
    async def f(u):
        n["c"] += 1
        if n["c"] < 3: raise ConnectionError("boom")
        return "ok"
    return run(S.fetch_all(["a"], f, retries=2)) == ["ok"] and n["c"] == 3
def retry_exhausted():
    n = {"c": 0}
    async def f(u):
        n["c"] += 1; raise TimeoutError(f"t{n['c']}")
    r = run(S.fetch_all(["a"], f, retries=2)); return isinstance(r[0], TimeoutError) and str(r[0]) == "t3" and n["c"] == 3
def retries0():
    n = {"c": 0}
    async def f(u):
        n["c"] += 1; raise ValueError("x")
    r = run(S.fetch_all(["a"], f, retries=0)); return isinstance(r[0], ValueError) and n["c"] == 1
def mixed():
    async def f(u):
        if u == "bad": raise ValueError("bad")
        return u
    r = run(S.fetch_all(["x", "bad", "y"], f, retries=1)); return r[0] == "x" and isinstance(r[1], ValueError) and r[2] == "y"
def dupes():
    t = T(); r = run(S.fetch_all(["u1", "u1"], t.fetch)); return r == ["U1", "U1"] and t.calls["u1"] == 2
def empty():
    t = T(); return run(S.fetch_all([], t.fetch)) == []
def badlimit():
    t = T(); return raises(ValueError, lambda: run(S.fetch_all(["a"], t.fetch, limit=0)))
check("order preserved", order)
check("concurrency reaches limit=3 exactly", limit3)
check("limit=1 is sequential", limit1)
check("retry then succeed", retry_ok)
check("exhausted retries -> last exception returned", retry_exhausted)
check("retries=0 means one attempt", retries0)
check("one failure doesn't affect others", mixed)
check("duplicate urls fetched independently", dupes)
check("empty list", empty)
check("limit < 1 -> ValueError", badlimit)
