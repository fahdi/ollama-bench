"""Real-world coding scenarios. Each code scenario has a spec (shown to the model) and hidden checks (never shown)."""

PY_HEAD = '''import sys
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
'''

PHP_HEAD = '''<?php
function canon($a) { if (!is_array($a)) return $a; if (!array_is_list($a)) ksort($a); foreach ($a as $k => $v) $a[$k] = canon($v); return $a; }
function same($a, $b) { return canon($a) === canon($b); }
function check($name, $fn) { try { $ok = (bool)$fn(); } catch (Throwable $e) { $ok = false; } echo ($ok ? "PASS " : "FAIL ") . $name . "\\n"; }
require __DIR__ . '/solution.php';
$f = 'travel_itinerary_query_args';
'''

WP_STUBS = r'''<?php
if (!function_exists('absint')) { function absint($v) { return abs((int)$v); } }
if (!function_exists('sanitize_text_field')) { function sanitize_text_field($s) { return trim(preg_replace('/[\r\n\t ]+/', ' ', strip_tags((string)$s))); } }
if (!function_exists('sanitize_title')) { function sanitize_title($s) { $s = strtolower(strip_tags((string)$s)); $s = preg_replace('/[^a-z0-9\s_-]/', '', $s); $s = preg_replace('/[\s_-]+/', '-', trim($s)); return trim($s, '-'); } }
'''

SCENARIOS = []

# ---------------------------------------------------------------- 1. nginx log analysis
SCENARIOS.append(dict(id="py_nginx_logs", lang="python", title="Parse nginx access logs, find failing endpoints", spec='''Our on-call team needs a small Python 3.12 module to triage nginx access logs.

Write `solution.py` with:

1. `parse_line(line: str) -> dict | None`
   Parses one line in nginx "combined" format, e.g.
   `127.0.0.1 - - [10/Oct/2026:13:55:36 +0000] "GET /api/users?id=5 HTTP/1.1" 502 1234 "-" "curl/8.0"`
   Returns a dict with keys:
   - "ip": str
   - "time": timezone-aware datetime, keeping the offset from the log (+0000, +0500, ...)
   - "method": str
   - "path": str, WITHOUT the query string
   - "status": int
   - "bytes": int (0 when the field is "-")
   The remote-user field may be a name instead of "-". The user agent may contain spaces.
   Returns None (never raises) for any malformed line: empty, garbage, non-numeric status, an unparseable timestamp,
   or a request field that is not exactly "METHOD PATH PROTOCOL" (nginx writes "-" for bad requests).

2. `top_error_paths(lines, n: int = 3) -> list[tuple[str, int]]`
   Takes an iterable of raw lines. Counts responses with status >= 500 per path (query string stripped),
   ignoring malformed lines. Returns the top n as (path, count), sorted by count descending, then path ascending.
''', hidden=PY_HEAD + r'''
from datetime import timedelta, timezone
L1 = '127.0.0.1 - - [10/Oct/2026:13:55:36 +0000] "GET /api/users?id=5 HTTP/1.1" 502 1234 "-" "curl/8.0"'
L2 = '10.0.0.2 - bob [10/Oct/2026:18:55:36 +0500] "POST /login HTTP/1.1" 200 - "https://x.com/" "Mozilla/5.0 (X11; Linux x86_64)"'
def mk(path, status): return f'1.1.1.1 - - [10/Oct/2026:13:55:36 +0000] "GET {path} HTTP/1.1" {status} 10 "-" "ua"'
check("basic fields", lambda: (lambda r: r["ip"] == "127.0.0.1" and r["method"] == "GET" and r["status"] == 502 and r["bytes"] == 1234)(S.parse_line(L1)))
check("query string stripped", lambda: S.parse_line(L1)["path"] == "/api/users")
check("time aware and correct", lambda: (lambda t: t.utcoffset() == timedelta(0) and (t.year, t.month, t.day, t.hour, t.minute, t.second) == (2026, 10, 10, 13, 55, 36))(S.parse_line(L1)["time"]))
check("+0500 offset kept", lambda: S.parse_line(L2)["time"].utcoffset() == timedelta(hours=5))
check("same instant across zones", lambda: S.parse_line(L2)["time"].astimezone(timezone.utc).hour == 13)
check("bytes '-' -> 0, named user, UA with spaces", lambda: (lambda r: r["bytes"] == 0 and r["path"] == "/login" and r["method"] == "POST")(S.parse_line(L2)))
check("malformed -> None", lambda: all(S.parse_line(x) is None for x in ["", "garbage", mk("/", "abc"), '1.2.3.4 - - [10/Oct/2026:13:55:36 +0000] "-" 400 0 "-" "-"', '1.2.3.4 - - [99/Foo/2026:13:55:36 +0000] "GET / HTTP/1.1" 200 1 "-" "-"']))
LINES = [mk("/a?x=1", 500), mk("/a", 502), mk("/a?y", 503), mk("/b", 500), mk("/b", 504), mk("/b", 500), mk("/c", 500), mk("/d", 404), mk("/d", 404), mk("/d", 404), mk("/d", 404), "junk line"]
check("top n with tie-break by path", lambda: S.top_error_paths(LINES, 2) == [("/a", 3), ("/b", 3)])
check("default n=3 and 4xx ignored", lambda: S.top_error_paths(LINES) == [("/a", 3), ("/b", 3), ("/c", 1)])
check("n larger than data", lambda: S.top_error_paths(LINES, 10) == [("/a", 3), ("/b", 3), ("/c", 1)])
check("accepts a generator", lambda: S.top_error_paths((l for l in LINES), 1) == [("/a", 3)])
'''))

# ---------------------------------------------------------------- 2. async fetcher
SCENARIOS.append(dict(id="py_async_fetch", lang="python", title="Concurrency-limited async fetcher with retries", spec='''We scrape partner APIs and keep getting rate-limited. Write `solution.py` (Python 3.12, standard library only) with:

`async def fetch_all(urls: list[str], fetch, limit: int = 5, retries: int = 2) -> list`

- `fetch` is an async callable: `await fetch(url)` returns a result or raises an exception.
- At most `limit` calls to `fetch` may be in flight at any moment, and the function should actually use that concurrency (don't run things one by one when limit > 1).
- If a call raises any Exception, retry that url immediately, up to `retries` additional attempts (so at most retries + 1 attempts per url).
- Returns a list in the same order as `urls`. Each element is the fetch result, or, if every attempt failed, the exception instance from the LAST attempt. `fetch_all` itself must not raise for fetch failures.
- Duplicate urls are fetched independently.
- `limit < 1` raises ValueError. An empty list returns [].
''', hidden=PY_HEAD + r'''
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
'''))

# ---------------------------------------------------------------- 3. legacy refactor + business bug fixes
SCENARIOS.append(dict(id="py_refactor_invoice", lang="python", title="Refactor legacy invoice code and fix two business bugs", spec='''This legacy function from our billing service is hard to read and has two bugs reported by finance.

```python
def calc(items, coupon=None, country="US"):
    t = 0
    for i in items:
        if i["qty"] > 0:
            t = t + i["price"] * i["qty"]
    if country == "US":
        tax = t * 0.08
    elif country == "PK":
        tax = t * 0.17
    else:
        tax = 0
    if coupon == "SAVE10":
        t = t - t * 0.10
    elif coupon == "FLAT5":
        t = t - 5
    total = t + tax
    return round(total, 2)
```

Rewrite it as clean, readable code in `solution.py`, keeping the name `calc` and the same signature, and fix:

1. Tax must be computed on the DISCOUNTED subtotal (currently it is computed before the discount).
2. FLAT5 must never make the subtotal negative (floor it at 0).

Also:
- An unknown coupon code must raise ValueError. `None` or "" means no coupon.
- Items with qty <= 0 are ignored (as today). Unknown countries pay no tax (as today).
- Use exact decimal arithmetic internally (no float drift) and round ONLY the final total to 2 places, rounding half up.
- Return a float.
''', hidden=PY_HEAD + r'''
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
'''))

# ---------------------------------------------------------------- 4. production bug from a traceback
SCENARIOS.append(dict(id="py_tz_bugfix", lang="python", title="Fix a production timezone crash from a traceback", spec='''Production is throwing this on every request to the subscriptions endpoint:

```
Traceback (most recent call last):
  File "/app/billing/subs.py", line 9, in is_active
    return start <= now < end
TypeError: can't compare offset-naive and offset-aware datetimes
```

Current code:

```python
from datetime import datetime, timedelta

def is_active(sub: dict, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    start = datetime.fromisoformat(sub["started_at"])
    end = start + timedelta(days=sub["period_days"])
    if sub.get("cancelled_at"):
        cancelled = datetime.fromisoformat(sub["cancelled_at"])
        return now < cancelled
    return start <= now < end
```

Facts from the investigation:
- Stored timestamps come in three shapes: with an offset ("2026-09-01T10:00:00+05:00"), with "Z", or naive. Naive stored timestamps are UTC.
- Callers may pass `now` naive (meaning UTC) or aware.
- Product also confirmed a second bug: cancelling must NOT end access early. A cancelled subscription stays active until the end of its current paid period.
- A subscription is active from started_at (inclusive) to started_at + period_days (exclusive).

Write the fixed `is_active` in `solution.py` (Python 3.12, standard library only). It must always return a bool.
''', hidden=PY_HEAD + r'''
from datetime import datetime, timezone, timedelta
U = timezone.utc
sub = {"started_at": "2026-09-01T10:00:00+05:00", "period_days": 30}
check("aware start, aware now inside", lambda: S.is_active(sub, datetime(2026, 9, 15, tzinfo=U)) is True)
check("just before start", lambda: S.is_active(sub, datetime(2026, 9, 1, 4, 59, tzinfo=U)) is False)
check("exactly at start (inclusive)", lambda: S.is_active(sub, datetime(2026, 9, 1, 5, 0, tzinfo=U)) is True)
check("exactly at end (exclusive)", lambda: S.is_active(sub, datetime(2026, 10, 1, 5, 0, tzinfo=U)) is False)
check("naive now treated as UTC", lambda: S.is_active(sub, datetime(2026, 10, 1, 4, 59)) is True)
check("Z suffix", lambda: S.is_active({"started_at": "2026-09-01T00:00:00Z", "period_days": 1}, datetime(2026, 9, 1, 12, tzinfo=U)) is True)
check("naive stored = UTC", lambda: S.is_active({"started_at": "2026-09-01T00:00:00", "period_days": 1}, datetime(2026, 9, 1, 23, 59, tzinfo=timezone(timedelta(hours=-1)))) is False)
check("cancelled stays active until period end", lambda: S.is_active({**sub, "cancelled_at": "2026-09-05T00:00:00Z"}, datetime(2026, 9, 20, tzinfo=U)) is True)
check("cancelled, after period end", lambda: S.is_active({**sub, "cancelled_at": "2026-09-05T00:00:00Z"}, datetime(2026, 10, 2, tzinfo=U)) is False)
check("default now works", lambda: S.is_active({"started_at": "2020-01-01T00:00:00Z", "period_days": 1}) is False)
'''))

# ---------------------------------------------------------------- 5. WordPress query args (travel site itinerary filters)
SCENARIOS.append(dict(id="php_wp_query", lang="php", title="WordPress itinerary filter -> WP_Query args", spec='''We are building the itinerary archive filters for a WordPress travel site (WP Travel plugin, post type `itineraries`).
Write `solution.php` defining:

`function travel_itinerary_query_args(array $request): array`

It turns the raw request array ($_GET) into WP_Query args. Rules:

- Always: 'post_type' => 'itineraries', 'post_status' => 'publish', 'posts_per_page' => 12.
- 'paged' => max(1, absint($request['page'] ?? 1)).
- Category: $request['category'] is a string of one or more comma-separated slugs. Trim each piece, run it through sanitize_title(), drop empty results. If any remain, add
  'tax_query' => [[ 'taxonomy' => 'itinerary_types', 'field' => 'slug', 'terms' => [...slugs in original order], 'operator' => 'IN' ]].
  Otherwise no 'tax_query' key at all.
- Duration: $request['min_days'] / $request['max_days']. A value is valid only if it is a non-negative integer given as an int or a digits-only string ("3" ok; "2.5", "-2", "abc" invalid). Invalid values are ignored.
  Add 'meta_query' => [[ 'key' => 'trip_duration', 'value' => ..., 'compare' => ..., 'type' => 'NUMERIC' ]]:
    both valid: value [min, max] (ints) and compare 'BETWEEN' (swap them if min > max);
    only min: value min (int), compare '>=';  only max: value max (int), compare '<='.
  If neither is valid, no 'meta_query' key at all.
- Sort: $request['sort'] is one of 'price_asc', 'price_desc', 'newest'.
    price_asc / price_desc: 'orderby' => 'meta_value_num', 'meta_key' => 'trip_price', 'order' => 'ASC' / 'DESC'.
    newest or anything else or missing: 'orderby' => 'date', 'order' => 'DESC' (no 'meta_key').
- Return no other keys.

The WordPress functions absint(), sanitize_title() and sanitize_text_field() are already loaded; call them, do not define them. PHP 8.3+.
''', hidden=PHP_HEAD + r'''
$base = ['post_type' => 'itineraries', 'post_status' => 'publish', 'posts_per_page' => 12, 'paged' => 1, 'orderby' => 'date', 'order' => 'DESC'];
check("defaults, exact keys", fn() => same($f([]), $base));
check("page parsed as int", fn() => $f(['page' => '3'])['paged'] === 3);
check("page 0 / garbage -> 1", fn() => $f(['page' => '0'])['paged'] === 1 && $f(['page' => 'abc'])['paged'] === 1);
check("single category sanitized", fn() => same($f(['category' => 'Family Trips'])['tax_query'], [['taxonomy' => 'itinerary_types', 'field' => 'slug', 'terms' => ['family-trips'], 'operator' => 'IN']]));
check("multi category, empties dropped, order kept", fn() => $f(['category' => 'girlfriend-getaway, ,Shopping & Spa,'])['tax_query'][0]['terms'] === ['girlfriend-getaway', 'shopping-spa']);
check("empty category -> no tax_query key", fn() => !array_key_exists('tax_query', $f(['category' => ' , '])));
check("duration BETWEEN", fn() => same($f(['min_days' => '2', 'max_days' => '5'])['meta_query'], [['key' => 'trip_duration', 'value' => [2, 5], 'compare' => 'BETWEEN', 'type' => 'NUMERIC']]));
check("min > max swapped", fn() => $f(['min_days' => 5, 'max_days' => '2'])['meta_query'][0]['value'] === [2, 5]);
check("only min", fn() => same($f(['min_days' => '3'])['meta_query'], [['key' => 'trip_duration', 'value' => 3, 'compare' => '>=', 'type' => 'NUMERIC']]));
check("only max (invalid min ignored)", fn() => same($f(['min_days' => '2.5', 'max_days' => '7'])['meta_query'], [['key' => 'trip_duration', 'value' => 7, 'compare' => '<=', 'type' => 'NUMERIC']]));
check("all invalid durations -> no meta_query key", fn() => !array_key_exists('meta_query', $f(['min_days' => 'abc', 'max_days' => '-2'])));
check("sort price_asc", fn() => (fn($a) => $a['orderby'] === 'meta_value_num' && $a['meta_key'] === 'trip_price' && $a['order'] === 'ASC')($f(['sort' => 'price_asc'])));
check("sort price_desc", fn() => (fn($a) => $a['orderby'] === 'meta_value_num' && $a['order'] === 'DESC')($f(['sort' => 'price_desc'])));
check("unknown sort -> newest, no meta_key", fn() => (fn($a) => $a['orderby'] === 'date' && $a['order'] === 'DESC' && !array_key_exists('meta_key', $a))($f(['sort' => "x'; DROP TABLE wp_posts;--"])));
check("full request exact", fn() => same($f(['page' => '2', 'category' => 'family', 'min_days' => '1', 'max_days' => '3', 'sort' => 'price_desc', 'evil' => '1']), ['post_type' => 'itineraries', 'post_status' => 'publish', 'posts_per_page' => 12, 'paged' => 2, 'tax_query' => [['taxonomy' => 'itinerary_types', 'field' => 'slug', 'terms' => ['family'], 'operator' => 'IN']], 'meta_query' => [['key' => 'trip_duration', 'value' => [1, 3], 'compare' => 'BETWEEN', 'type' => 'NUMERIC']], 'orderby' => 'meta_value_num', 'meta_key' => 'trip_price', 'order' => 'DESC']));
'''))

# ---------------------------------------------------------------- 6. TypeScript cart reducer
SCENARIOS.append(dict(id="ts_cart_reducer", lang="ts", title="TypeScript shopping-cart reducer (immutable, typed)", spec='''Write `solution.ts` for our React checkout: a pure reducer plus a totals helper. Use exactly these exported types:

```ts
export type CartItem = { sku: string; name: string; unitCents: number; qty: number };
export type CartState = { items: CartItem[]; coupon: string | null };
export type CartAction =
  | { type: "add"; item: { sku: string; name: string; unitCents: number }; qty?: number }
  | { type: "remove"; sku: string }
  | { type: "setQty"; sku: string; qty: number }
  | { type: "applyCoupon"; code: string }
  | { type: "clear" };
```

Export `cartReducer(state: CartState, action: CartAction): CartState`:
- add: qty defaults to 1 and must be a positive integer, otherwise return `state` unchanged (same reference). If the sku is already in the cart, increase its qty; otherwise append it.
- remove: remove the sku. Unknown sku: return `state` (same reference).
- setQty: qty <= 0 removes the item. Unknown sku: return `state` (same reference).
- applyCoupon: codes are case-insensitive. Valid codes: "SAVE10", "HALFOFF"; store the uppercase code. Unknown code: return `state` (same reference).
- clear: `{ items: [], coupon: null }`.
- NEVER mutate the input state or its items (callers may pass frozen objects). Keep item order.

Export `cartTotals(state: CartState): { subtotalCents: number; discountCents: number; taxCents: number; totalCents: number }`:
- subtotal = sum(unitCents * qty)
- discount: SAVE10 = Math.floor(subtotal * 0.10); HALFOFF = Math.min(Math.floor(subtotal * 0.5), 2000); none = 0
- tax = Math.round((subtotal - discount) * 0.08)
- total = subtotal - discount + tax

Must compile under `tsc --strict`. Node runs the file with type stripping, so no enums, namespaces, or parameter properties.
''', hidden=r'''import { cartReducer, cartTotals } from "./solution.ts";
import type { CartState, CartAction } from "./solution.ts";
function check(name: string, fn: () => boolean): void { let ok = false; try { ok = fn(); } catch { ok = false; } console.log(`${ok ? "PASS" : "FAIL"} ${name}`); }
function freeze<T>(o: T): T { if (o && typeof o === "object") { Object.values(o as object).forEach(freeze); Object.freeze(o); } return o; }
const empty: CartState = freeze({ items: [], coupon: null });
const A = { sku: "A", name: "Apple", unitCents: 250 };
const B = { sku: "B", name: "Bread", unitCents: 1000 };
const step = (s: CartState, a: CartAction): CartState => freeze(cartReducer(freeze(s), a));
const AB = step(step(step(empty, { type: "add", item: A }), { type: "add", item: A }), { type: "add", item: B });
check("add new item, qty defaults to 1", () => { const s = step(empty, { type: "add", item: A }); return s.items.length === 1 && s.items[0].qty === 1 && s !== empty; });
check("add existing increments (frozen input)", () => { const s = step(step(empty, { type: "add", item: A }), { type: "add", item: A, qty: 3 }); return s.items.length === 1 && s.items[0].qty === 4; });
check("add qty 0 -> same reference", () => cartReducer(AB, { type: "add", item: A, qty: 0 }) === AB);
check("item order kept", () => AB.items.map(i => i.sku).join() === "A,B");
check("setQty updates", () => step(AB, { type: "setQty", sku: "B", qty: 5 }).items[1].qty === 5);
check("setQty 0 removes", () => step(AB, { type: "setQty", sku: "A", qty: 0 }).items.map(i => i.sku).join() === "B");
check("remove existing", () => step(AB, { type: "remove", sku: "A" }).items.length === 1);
check("remove unknown -> same reference", () => cartReducer(AB, { type: "remove", sku: "Z" }) === AB);
check("coupon case-insensitive, stored uppercase", () => step(AB, { type: "applyCoupon", code: "save10" }).coupon === "SAVE10");
check("unknown coupon -> same reference", () => cartReducer(AB, { type: "applyCoupon", code: "FREE" }) === AB);
check("clear", () => { const s = step(step(AB, { type: "applyCoupon", code: "SAVE10" }), { type: "clear" }); return s.items.length === 0 && s.coupon === null; });
check("totals, no coupon", () => JSON.stringify(cartTotals(AB)) === JSON.stringify({ subtotalCents: 1500, discountCents: 0, taxCents: 120, totalCents: 1620 }));
check("totals, SAVE10", () => { const t = cartTotals(step(AB, { type: "applyCoupon", code: "SAVE10" })); return t.discountCents === 150 && t.taxCents === 108 && t.totalCents === 1458; });
check("totals, HALFOFF capped at 2000", () => { const s = step(step(empty, { type: "add", item: B, qty: 5 }), { type: "applyCoupon", code: "HALFOFF" }); const t = cartTotals(s); return t.discountCents === 2000 && t.taxCents === 240 && t.totalCents === 3240; });
check("tax rounding", () => { const s = step(empty, { type: "add", item: { sku: "C", name: "C", unitCents: 1234 } }); const t = cartTotals(s); return t.taxCents === 99 && t.totalCents === 1333; });
'''))

# ---------------------------------------------------------------- 7. Rust semver
SCENARIOS.append(dict(id="rust_semver", lang="rust", title="Rust semver parser and range matcher", spec='''Our Rust release tool needs dependency-range checks. Write `solution.rs` (a module, std only, no external crates, no `fn main`) with:

```rust
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct Version { pub major: u64, pub minor: u64, pub patch: u64 }
pub fn parse(s: &str) -> Result<Version, String>
pub fn satisfies(v: &Version, req: &str) -> Result<bool, String>
```

parse:
- Accepts "MAJOR.MINOR.PATCH", optionally prefixed with "v", surrounding whitespace ignored.
- Rejects: leading zeros ("01.2.3"; plain "0" is fine), missing or extra parts, empty parts, non-digits, signs, and pre-release/build suffixes like "1.2.3-beta".

satisfies: `req` is one or more comparators separated by commas (whitespace around commas optional), ALL of which must match. Comparator forms:
- "1.2.3" or "=1.2.3" exact; ">1.2.3", ">=1.2.3", "<1.2.3", "<=1.2.3"
- "~1.2.3": >=1.2.3 and <1.3.0
- "^1.2.3": >=1.2.3 and <2.0.0. For major 0: "^0.2.3" means >=0.2.3 <0.3.0, and "^0.0.3" means exactly 0.0.3.
Any malformed requirement returns Err.
''', hidden=r'''#![allow(warnings)]
#[path = "solution.rs"] mod solution;
use solution::*;
use std::panic;
fn check(name: &str, f: impl FnOnce() -> bool + panic::UnwindSafe) { let ok = panic::catch_unwind(f).unwrap_or(false); println!("{} {}", if ok { "PASS" } else { "FAIL" }, name); }
fn v(a: u64, b: u64, c: u64) -> Version { Version { major: a, minor: b, patch: c } }
fn main() {
    panic::set_hook(Box::new(|_| {}));
    check("parse basic", || parse("1.2.3") == Ok(v(1, 2, 3)));
    check("parse v prefix + whitespace", || parse(" v10.20.30 ") == Ok(v(10, 20, 30)));
    check("zeros allowed", || parse("0.0.0") == Ok(v(0, 0, 0)));
    check("reject leading zeros", || parse("01.2.3").is_err() && parse("1.02.3").is_err());
    check("reject bad shapes", || ["", "1.2", "1.2.3.4", "a.b.c", "1.2.-3", "1..3", "1.2.3-beta", "+1.2.3"].iter().all(|s| parse(s).is_err()));
    check("ordering", || v(1, 2, 3) < v(1, 10, 0) && v(2, 0, 0) > v(1, 99, 99));
    check("exact and =", || satisfies(&v(1, 2, 3), "1.2.3") == Ok(true) && satisfies(&v(1, 2, 4), "=1.2.3") == Ok(false));
    check("> >= < <=", || satisfies(&v(1, 5, 0), ">=1.2.3") == Ok(true) && satisfies(&v(2, 0, 0), "<2.0.0") == Ok(false) && satisfies(&v(2, 0, 0), "<=2.0.0") == Ok(true) && satisfies(&v(1, 2, 3), ">1.2.3") == Ok(false));
    check("caret", || satisfies(&v(1, 9, 9), "^1.2.3") == Ok(true) && satisfies(&v(2, 0, 0), "^1.2.3") == Ok(false) && satisfies(&v(1, 2, 2), "^1.2.3") == Ok(false));
    check("caret 0.x", || satisfies(&v(0, 2, 9), "^0.2.3") == Ok(true) && satisfies(&v(0, 3, 0), "^0.2.3") == Ok(false));
    check("caret 0.0.x", || satisfies(&v(0, 0, 3), "^0.0.3") == Ok(true) && satisfies(&v(0, 0, 4), "^0.0.3") == Ok(false));
    check("tilde", || satisfies(&v(1, 2, 9), "~1.2.3") == Ok(true) && satisfies(&v(1, 3, 0), "~1.2.3") == Ok(false));
    check("AND ranges", || satisfies(&v(1, 4, 9), ">=1.0.0, <1.5.0") == Ok(true) && satisfies(&v(1, 5, 0), ">=1.0.0,<1.5.0") == Ok(false));
    check("malformed req -> Err", || satisfies(&v(1, 0, 0), ">>1.0.0").is_err() && satisfies(&v(1, 0, 0), "^1.x").is_err() && satisfies(&v(1, 0, 0), "").is_err());
}
'''))

# ---------------------------------------------------------------- 8. bank CSV
SCENARIOS.append(dict(id="py_bank_csv", lang="python", title="Summarize a messy bank CSV export", spec='''Accounting sends us bank exports as CSV. Write `solution.py` (Python 3.12, standard library only) with:

`summarize(csv_text: str) -> dict[str, Decimal]`

- The header row names the columns: Date, Description, Category, Amount. Column ORDER varies between banks, and header names may differ in case and have surrounding spaces.
- Fields may be quoted and quoted fields may contain commas and doubled quotes. No field spans multiple lines.
- Amount formats: "1,234.56", "-45.00", "(45.00)" (negative), "$12.50", "-$5.00", with optional surrounding spaces.
- Blank lines are ignored. An empty Category becomes "Uncategorized".
- Sum amounts exactly per category, then quantize each total to 0.01 with ROUND_HALF_UP. Values are Decimal.
- An unparseable amount raises ValueError whose message contains "line N", where N is the 1-based physical line number in the text (header is line 1, blank lines count).
- A file with only a header returns {}.
''', hidden=PY_HEAD + r'''
def _err(text):
    try:
        S.summarize(text)
    except ValueError as e:
        return e
    except BaseException:
        return None
    return None
from decimal import Decimal as D
CSV = 'Date,Description,Category,Amount\n2026-09-01,"Coffee, large",Food,"$4.50"\n2026-09-02,Salary,Income,"2,500.00"\n2026-09-03,Refund,Food,(1.50)\n2026-09-04,Rent,Housing,-1200.00\n\n2026-09-05,"Misc ""quoted"" thing",,12.345\n2026-09-06,Fee,Housing, -$5.00 \n'
R = lambda: S.summarize(CSV)
check("food total", lambda: R()["Food"] == D("3.00"))
check("thousands separator", lambda: R()["Income"] == D("2500.00"))
check("negatives incl -$", lambda: R()["Housing"] == D("-1205.00"))
check("uncategorized + half-up", lambda: R()["Uncategorized"] == D("12.35"))
check("exactly 4 categories", lambda: len(R()) == 4)
check("values are Decimal", lambda: all(isinstance(x, D) for x in R().values()))
check("reordered, messy header", lambda: S.summarize(' amount , CATEGORY,date,Description\n"(10.00)",Food,2026-09-01,x\n20,Food,2026-09-02,y\n') == {"Food": D("10.00")})
check("bad amount -> ValueError with line", lambda: (lambda e: e is not None and "line 3" in str(e))(_err('Date,Description,Category,Amount\n2026-09-01,a,Food,1.00\n2026-09-02,b,Food,abc\n')))
check("header only -> {}", lambda: S.summarize("Date,Description,Category,Amount\n") == {})
'''))

# ---------------------------------------------------------------- non-TDD scenarios (graded directly)
SQL_SPEC = '''Write ONE SQLite query for our finance dashboard.

Schema:
```sql
CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
                     created_at TEXT NOT NULL,  -- ISO-8601 UTC, e.g. '2026-09-02T10:00:00Z'
                     status TEXT NOT NULL);     -- 'paid', 'refunded' or 'pending'
CREATE TABLE order_items (order_id INTEGER NOT NULL REFERENCES orders(id), sku TEXT NOT NULL,
                          qty INTEGER NOT NULL, unit_cents INTEGER NOT NULL);
```

Return the top 3 customers by revenue from PAID orders created in September 2026 (UTC).
Revenue = SUM(qty * unit_cents). Columns, in order: name, revenue_cents, order_count (number of distinct paid September orders).
Sort by revenue_cents descending, then name ascending. Reply with only the query in one ```sql block.'''

BASH_SPEC = '''Write a bash script `report.sh` for our ops team. It must run on stock macOS: /bin/bash 3.2 and BSD find/stat/sort (no GNU-only flags, no mapfile, no associative arrays).

Usage: `report.sh DIR DAYS MB`
- List every regular file under DIR (recursively) that is LARGER than MB megabytes (1 MB = 1048576 bytes; strictly greater) AND was last modified MORE than DAYS days ago.
- Output one line per file: `SIZE_IN_BYTES<TAB>PATH`, where PATH is how `find DIR ...` prints it (DIR as given by the caller).
- Sort by size descending.
- File names may contain spaces.
- Never modify or delete anything.
- If any argument is missing, print a usage line to stderr and exit with status 2.
Reply with only the script in one ```bash block.'''

TOOLS = [
    {"type": "function", "function": {"name": "get_weather", "description": "Current weather for a city",
     "parameters": {"type": "object", "properties": {"city": {"type": "string"}, "unit": {"type": "string", "enum": ["c", "f"]}}, "required": ["city"]}}},
    {"type": "function", "function": {"name": "convert_currency", "description": "Convert an amount between ISO-4217 currencies",
     "parameters": {"type": "object", "properties": {"amount": {"type": "number"}, "from": {"type": "string", "description": "ISO code, e.g. USD"}, "to": {"type": "string", "description": "ISO code"}}, "required": ["amount", "from", "to"]}}},
    {"type": "function", "function": {"name": "create_jira_ticket", "description": "Create a Jira ticket",
     "parameters": {"type": "object", "properties": {"project": {"type": "string", "description": "Project key"}, "summary": {"type": "string"}, "priority": {"type": "string", "enum": ["low", "medium", "high"]}}, "required": ["project", "summary", "priority"]}}},
]

REVIEW_SPEC = '''Review this pull request diff for a Flask API. List every real bug or security problem you find, each with a one-line fix. Be concise.

```diff
+@app.route("/api/projects/<int:project_id>/notes")
+def list_notes(project_id):
+    page = int(request.args.get("page", 1))      # pages are 1-based
+    size = 20
+    q = request.args.get("q", "")
+    sql = f"SELECT id, body FROM notes WHERE project_id = {project_id} AND body LIKE '%{q}%' LIMIT {size} OFFSET {page * size}"
+    rows = db.execute(sql).fetchall()
+    return jsonify([dict(r) for r in rows])
+
+@app.route("/api/notes/<int:note_id>", methods=["DELETE"])
+@login_required
+def delete_note(note_id):
+    note = Note.query.get_or_404(note_id)
+    db.session.delete(note)
+    db.session.commit()
+    return "", 204
+
+@app.route("/api/billing/charge", methods=["POST"])
+@login_required
+def charge():
+    try:
+        gateway.charge(current_user.customer_id, request.json["amount_cents"])
+    except:
+        pass
+    return jsonify({"ok": True})
```'''
