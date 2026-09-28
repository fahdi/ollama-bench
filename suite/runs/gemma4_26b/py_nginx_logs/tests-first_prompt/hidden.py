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
