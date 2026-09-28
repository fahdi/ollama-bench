"""Run real-world scenarios against local Ollama models: one-shot vs tests-first prompt vs real TDD loop, graded by hidden tests."""
import json, os, random, re, shutil, sqlite3, subprocess, sys, time, urllib.request
from pathlib import Path
from scenarios import SCENARIOS, WP_STUBS, SQL_SPEC, BASH_SPEC, TOOLS, REVIEW_SPEC

API = "http://localhost:11434/api"
HERE = Path(__file__).parent.resolve()
RUNS = HERE / "runs"
STUBS = HERE / "wp_stubs.php"
STUBS.write_text(WP_STUBS)
TSC = HERE / "node_modules" / ".bin" / "tsc"
MAX_FIX_ROUNDS = 3

MODELS = {
    "gemma4:26b": {"think": False},
    "qwen3-coder:30b": {},
}

LANGS = {
    "python": dict(sol="solution.py", test="test_solution.py", run="python3 -m unittest -v test_solution",
                   stub="the required functions with the correct signatures whose bodies just `raise NotImplementedError`",
                   hint="Use the standard library `unittest` module (no pytest). Import from `solution`."),
    "php": dict(sol="solution.php", test="test_solution.php", run=f"php -d auto_prepend_file={STUBS} test_solution.php",
                stub="the required function with the correct signature whose body just throws `new \\LogicException('not implemented')`",
                hint="PHPUnit is not available: write a plain PHP script that requires solution.php, runs your assertions, prints each failure, and ends with exit(1) if anything failed, exit(0) otherwise. The WordPress functions are auto-loaded; do not define them."),
    "ts": dict(sol="solution.ts", test="solution.test.ts", run="node --test solution.test.ts",
               stub="the exported types and functions with the correct signatures whose bodies just `throw new Error('not implemented')`",
               hint="Use `node:test` and `node:assert/strict`. Import with the .ts extension: `from \"./solution.ts\"`."),
    "rust": dict(sol="solution.rs", test=None, run="rustc --edition 2021 --test solution.rs -o t_bin 2>&1 && ./t_bin",
                 stub="the required items with the correct signatures whose function bodies are `todo!()`",
                 hint="Put the tests in a `#[cfg(test)] mod tests` at the bottom of solution.rs."),
}

FMT = "Output each file as a line `### FILE: <path>` followed immediately by one fenced code block containing the complete file."


# ------------------------------------------------------------------ plumbing
def chat(model, messages, tools=None, num_ctx=32768):
    body = {"model": model, "stream": False, "keep_alive": "15m", "messages": messages,
            "options": {"num_ctx": num_ctx, "temperature": 0, "num_predict": 8192}, **MODELS[model]}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(f"{API}/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    t = time.time()
    with urllib.request.urlopen(req, timeout=3600) as r:
        out = json.loads(r.read())
    out["wall"] = time.time() - t
    return out


def unload(model):
    try:
        urllib.request.urlopen(urllib.request.Request(f"{API}/generate", json.dumps({"model": model, "keep_alive": 0}).encode()))
    except Exception:
        pass


def extract(text, dest, expected=None):
    files = re.findall(r"###\s*FILE:\s*`?([^\s`]+)`?\s*\n+```[^\n]*\n(.*?)^```", text, re.S | re.M)
    if not files and expected and len(expected) == 1:
        m = re.search(r"```[^\n]*\n(.*?)^```", text, re.S | re.M)
        if m:
            files = [(expected[0], m.group(1))]
    for path, body in files:
        p = dest / path.strip().lstrip("./")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return [f[0] for f in files]


def sh(cmd, cwd, timeout=120):
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr)
    except subprocess.TimeoutExpired as e:
        return 124, f"TIMEOUT after {timeout}s\n{(e.stdout or b'')[-1500:]}"


def tail(s, n=2500):
    return s if len(s) <= n else "...(truncated)...\n" + s[-n:]


# ------------------------------------------------------------------ hidden grading for code scenarios
def expected_checks(sc):
    return len(re.findall(r"^\s*check\(", sc["hidden"], re.M))


def grade_hidden(sc, d):
    lang = sc["lang"]
    total = expected_checks(sc)
    extra = []
    if lang == "python":
        (d / "hidden.py").write_text(sc["hidden"]); _, out = sh("python3 hidden.py", d, 90)
    elif lang == "php":
        (d / "hidden.php").write_text(sc["hidden"]); _, out = sh(f"php -d auto_prepend_file={STUBS} hidden.php", d)
    elif lang == "ts":
        (d / "hidden.ts").write_text(sc["hidden"]); (d / "package.json").write_text('{"type":"module"}')
        rc, tout = sh(f"{TSC} --strict --noEmit --target es2022 --module nodenext --moduleResolution nodenext --allowImportingTsExtensions --lib es2022,dom --skipLibCheck hidden.ts", d)
        extra = [("typechecks under tsc --strict", rc == 0)]
        total += 1
        _, out = sh("node hidden.ts", d)
    elif lang == "rust":
        (d / "hidden.rs").write_text(sc["hidden"]); _, out = sh("rustc --edition 2021 hidden.rs -o h_bin 2>&1 && ./h_bin", d)
    results = [(m.group(2), m.group(1) == "PASS") for m in re.finditer(r"^(PASS|FAIL) (.+)$", out, re.M)] + extra
    passed = sum(ok for _, ok in results)
    (d / "_hidden_output.txt").write_text(out)
    return passed, total, results


# ------------------------------------------------------------------ arms
def arm_oneshot(model, sc, d, log):
    L = LANGS[sc["lang"]]
    msgs = [{"role": "user", "content": f"{sc['spec']}\n\nWrite `{L['sol']}`. {FMT}"}]
    r = chat(model, msgs); log.append(r)
    extract(r["message"]["content"], d, [L["sol"]])
    return {"turns": 1}


def arm_tests_first_prompt(model, sc, d, log):
    L = LANGS[sc["lang"]]
    files = f"`{L['test']}` and then `{L['sol']}`" if L["test"] else f"`{L['sol']}` containing the tests module and the implementation"
    msgs = [{"role": "user", "content": f"{sc['spec']}\n\nWork test-first: first write thorough tests for this spec (normal cases, edge cases, errors), then write the implementation that makes them pass. {L['hint']}\nOutput {files}. {FMT}"}]
    r = chat(model, msgs); log.append(r)
    extract(r["message"]["content"], d, [L["sol"]])
    return {"turns": 1}


def arm_tdd_loop(model, sc, d, log):
    L = LANGS[sc["lang"]]
    if L["test"]:
        step1 = (f"We will work strictly test-driven (TDD), in steps.\n\nSTEP 1 (now): write the test file `{L['test']}` with thorough tests "
                 f"for the spec (normal cases, edge cases, error cases), and a stub `{L['sol']}` containing {L['stub']}. Do NOT implement anything yet. "
                 f"{L['hint']}\nOutput both files. {FMT}")
    else:
        step1 = (f"We will work strictly test-driven (TDD), in steps.\n\nSTEP 1 (now): write `{L['sol']}` containing {L['stub']}, plus thorough tests "
                 f"for the spec (normal cases, edge cases, error cases). Do NOT implement anything yet. {L['hint']}\nOutput the file. {FMT}")
    msgs = [{"role": "user", "content": f"{sc['spec']}\n\n{step1}"}]
    r = chat(model, msgs); log.append(r); msgs.append(r["message"])
    extract(r["message"]["content"], d)
    rc, out = sh(L["run"], d)
    red = rc != 0
    msgs.append({"role": "user", "content": f"Test run against the stub (these are expected to fail):\n```\n{tail(out)}\n```\n\nSTEP 2: now write the real implementation in `{L['sol']}` so the tests pass"
                 + (" (keep the tests module)." if not L["test"] else ".") + f" Output only the files you change. {FMT}"})
    rounds, green = 0, False
    while True:
        r = chat(model, msgs); log.append(r); msgs.append(r["message"])
        extract(r["message"]["content"], d, [L["sol"]])
        rc, out = sh(L["run"], d)
        if rc == 0:
            green = True
            break
        if rounds >= MAX_FIX_ROUNDS:
            break
        rounds += 1
        msgs.append({"role": "user", "content": f"The tests fail:\n```\n{tail(out)}\n```\n\nFix the implementation. If a test itself contradicts the spec, fix that test instead and say so. Output only the files you change. {FMT}"})
    return {"turns": len(log), "red_first": red, "own_tests_green": green, "fix_rounds": rounds}


ARMS = {"one-shot": arm_oneshot, "tests-first prompt": arm_tests_first_prompt, "TDD loop": arm_tdd_loop}


# ------------------------------------------------------------------ non-TDD graders
def run_sql(model, d, log):
    r = chat(model, [{"role": "user", "content": SQL_SPEC}]); log.append(r)
    m = re.search(r"```(?:sql)?\s*\n(.*?)```", r["message"]["content"], re.S)
    q = (m.group(1) if m else r["message"]["content"]).strip()
    (d / "query.sql").write_text(q)
    db = sqlite3.connect(":memory:")
    db.executescript("""CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE order_items (order_id INTEGER NOT NULL, sku TEXT NOT NULL, qty INTEGER NOT NULL, unit_cents INTEGER NOT NULL);
INSERT INTO customers VALUES (1,'Aisha'),(2,'Bilal'),(3,'Chen'),(4,'Dana'),(5,'Emre');
INSERT INTO orders VALUES (101,1,'2026-09-02T10:00:00Z','paid'),(102,1,'2026-09-15T08:00:00Z','paid'),(103,2,'2026-09-10T00:00:00Z','paid'),
 (104,2,'2026-09-11T00:00:00Z','refunded'),(105,3,'2026-08-31T23:59:59Z','paid'),(106,3,'2026-09-30T23:59:59Z','paid'),
 (107,4,'2026-10-01T00:00:00Z','paid'),(108,4,'2026-09-20T12:00:00Z','pending'),(109,5,'2026-09-05T00:00:00Z','paid');
INSERT INTO order_items VALUES (101,'A',2,1000),(101,'B',1,500),(102,'A',1,1000),(103,'C',5,700),(104,'C',10,700),(105,'A',10,1000),
 (106,'B',1,500),(106,'B',2,500),(107,'A',50,1000),(108,'A',50,1000),(109,'D',1,4000);""")
    try:
        rows = [tuple(x) for x in db.execute(q).fetchall()]
        ran = True
    except Exception as e:
        rows, ran = [], False
    exp = [("Emre", 4000, 1), ("Aisha", 3500, 2), ("Bilal", 3500, 1)]
    res = [("query runs", ran), ("exactly 3 rows x 3 columns", len(rows) == 3 and all(len(x) == 3 for x in rows)),
           ("top row correct", rows[:1] == exp[:1]), ("tie broken by name", [x[0] for x in rows] == ["Emre", "Aisha", "Bilal"]),
           ("order_count counts distinct orders", len(rows) > 1 and rows[1][2:] == (2,)),
           ("refunded/pending/boundary dates excluded", ran and not any(x[0] in ("Chen", "Dana") for x in rows) and all(x[1] <= 4000 for x in rows)),
           ("exact result", rows == exp)]
    return res


def run_bash(model, d, log):
    r = chat(model, [{"role": "user", "content": BASH_SPEC}]); log.append(r)
    m = re.search(r"```(?:bash|sh)?\s*\n(.*?)```", r["message"]["content"], re.S)
    (d / "report.sh").write_text(m.group(1) if m else "")
    fx = d / "fixture"; shutil.rmtree(fx, ignore_errors=True); (fx / "sub dir").mkdir(parents=True)
    now = time.time(); MB = 1048576
    spec = [("old big.bin", 3 * MB, 40), ("sub dir/old huge.log", 5 * MB, 100), ("new big.bin", 3 * MB, 0), ("old small.txt", 10240, 40), ("exact2mb.bin", 2 * MB, 40)]
    for name, size, age in spec:
        p = fx / name
        with open(p, "wb") as f:
            f.truncate(size)
        os.utime(p, (now - age * 86400, now - age * 86400))
    before = sorted(str(p) for p in fx.rglob("*"))
    rc, out = sh(f'/bin/bash report.sh "{fx}" 30 2', d, 60)
    p = subprocess.run(f'/bin/bash report.sh "{fx}"', shell=True, cwd=d, capture_output=True, text=True, timeout=30)
    exp = f"{5 * MB}\t{fx}/sub dir/old huge.log\n{3 * MB}\t{fx}/old big.bin"
    lines = out.strip().splitlines()
    return [("exits 0", rc == 0), ("finds both old large files (spaces in names)", f"{fx}/sub dir/old huge.log" in out and f"{fx}/old big.bin" in out),
            ("excludes new, small and exactly-2MB files", "new big" not in out and "old small" not in out and "exact2mb" not in out),
            ("sorted by size desc, exact format", out.strip() == exp), ("nothing modified or deleted", sorted(str(p) for p in fx.rglob("*")) == before),
            ("missing args -> exit 2 + usage on stderr", p.returncode == 2 and p.stderr.strip() != "")]


def calls(r):
    return [(c["function"]["name"], c["function"].get("arguments") or {}) for c in (r["message"].get("tool_calls") or [])]


def run_tools(model, d, log):
    res = []
    r = chat(model, [{"role": "user", "content": "What's the weather in Lahore right now, in fahrenheit?"}], TOOLS); log.append(r)
    c = calls(r)
    res.append(("single call with right args", len(c) == 1 and c[0][0] == "get_weather" and str(c[0][1].get("city", "")).lower() == "lahore" and c[0][1].get("unit") == "f"))
    r = chat(model, [{"role": "user", "content": "Convert 250 US dollars to Pakistani rupees, and also tell me the weather in Karachi."}], TOOLS); log.append(r)
    c = dict(calls(r))
    cc = c.get("convert_currency", {})
    res.append(("two parallel calls", "convert_currency" in c and "get_weather" in c))
    res.append(("currency args: number + ISO codes", isinstance(cc.get("amount"), (int, float)) and cc.get("amount") == 250 and str(cc.get("from")).upper() == "USD" and str(cc.get("to")).upper() == "PKR"))
    r = chat(model, [{"role": "user", "content": "File a high priority bug in APP: the login button does nothing on iOS 19."}], TOOLS); log.append(r)
    c = calls(r)
    res.append(("jira ticket args", len(c) == 1 and c[0][0] == "create_jira_ticket" and c[0][1].get("project") == "APP" and c[0][1].get("priority") == "high" and "login" in str(c[0][1].get("summary", "")).lower()))
    r = chat(model, [{"role": "user", "content": "What is 17 * 3? Answer directly."}], TOOLS); log.append(r)
    res.append(("no tool call when not needed", not calls(r) and "51" in r["message"]["content"]))
    msgs = [{"role": "user", "content": "What's the weather in Lahore?"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "get_weather", "arguments": {"city": "Lahore"}}}]},
            {"role": "tool", "content": json.dumps({"city": "Lahore", "temp": 34, "unit": "c", "condition": "haze", "aqi": 212})}]
    r = chat(model, msgs, TOOLS); log.append(r)
    t = r["message"]["content"].lower()
    res.append(("uses tool result in answer", "34" in t and "haze" in t and not calls(r)))
    return res


def make_codebase():
    rnd = random.Random(7)
    words = ["user", "order", "invoice", "cart", "session", "token", "report", "export", "audit", "cache", "queue", "webhook", "coupon", "address", "shipment"]
    files = {}
    for i in range(30):
        mod = f"{rnd.choice(words)}_{rnd.choice(['service', 'utils', 'handlers', 'models', 'tasks'])}_{i}.py"
        body = [f'"""{mod} - internal module."""', "import logging", "log = logging.getLogger(__name__)", ""]
        for j in range(5):
            a, b = rnd.sample(words, 2)
            body += [f"def {a}_{b}_{j}(payload, *, strict=False):", f'    """Normalise the {a} {b} payload."""', f"    items = payload.get('{a}s', [])",
                     f"    if strict and not items:", f"        raise ValueError('missing {a}s')", f"    total = sum(x.get('{b}_count', 0) for x in items)",
                     f"    log.debug('{a}/{b} total=%s', total)", f"    return {{'{a}': items, 'total': total, 'retries': {rnd.randint(1, 9)}}}", ""]
        files[f"app/{mod}"] = "\n".join(body)
    files["app/config/base.py"] = "PAYMENT_TIMEOUT_MS = 7300\nGATEWAY_RETRIES = 3\nRECEIPT_SENDER = 'billing@example.com'\n"
    files["app/config/staging.py"] = "from .base import *\nPAYMENT_TIMEOUT_MS = 9000\n"
    files["app/config/production.py"] = "from .base import *\nPAYMENT_TIMEOUT_MS = 12000\nGATEWAY_RETRIES = 5\n"
    files["app/config/__init__.py"] = "import importlib, os\nsettings = importlib.import_module(f'app.config.{os.environ.get(\"APP_ENV\", \"base\")}')\n"
    files["app/billing/gateway.py"] = ("from app.config import settings\nMAX_RETRIES = 3  # legacy default, unused\n\n"
        "def charge_card(customer_id, amount_cents):\n    return _post('/charge', {'c': customer_id, 'a': amount_cents},\n"
        "                 timeout_ms=settings.PAYMENT_TIMEOUT_MS, retries=settings.GATEWAY_RETRIES)\n")
    files["app/orders/checkout.py"] = ("from app.billing.gateway import charge_card\nfrom app.notify.email import send_receipt_email\n\n"
        "def finalize_order(order):\n    charge_card(order.customer_id, order.total_cents)\n    order.mark_paid()\n    send_receipt_email(order)\n\n"
        "def refund_order(order):\n    # TODO: should we call send_receipt_email here too? (see ticket APP-88)\n    order.mark_refunded()\n")
    files["app/notify/email.py"] = "def send_receipt_email(order):\n    ...\n"
    keys = list(files)
    rnd.shuffle(keys)
    return "\n\n".join(f"# ===== {k} =====\n{files[k]}" for k in keys)


def run_longctx(model, d, log):
    code = make_codebase()
    q = ("Here is our codebase:\n\n" + code + "\n\nAnswer from the code only. The app runs with APP_ENV=production. Reply with only a JSON object with keys: "
         '"timeout_ms" (int: the timeout charge_card uses in production), "timeout_file" (str: path of the file that sets it), '
         '"retries" (int: retries charge_card uses in production), "receipt_caller" (str: name of the only function that actually calls send_receipt_email).')
    r = chat(model, [{"role": "user", "content": q}]); log.append(r)
    t = r["message"]["content"]
    m = re.search(r"\{.*\}", t, re.S)
    try:
        a = json.loads(m.group(0)) if m else {}
    except Exception:
        a = {}
    return [(f"production timeout = 12000 (prompt {r.get('prompt_eval_count', 0)} tokens)", a.get("timeout_ms") == 12000),
            ("names config/production.py", "production.py" in str(a.get("timeout_file", ""))),
            ("production retries = 5 (not the legacy 3)", a.get("retries") == 5),
            ("receipt caller = finalize_order (not the TODO decoy)", a.get("receipt_caller") == "finalize_order")]


def run_review(model, d, log):
    r = chat(model, [{"role": "user", "content": REVIEW_SPEC}]); log.append(r)
    t = r["message"]["content"].lower()
    return [("SQL injection", "injection" in t or "parameteriz" in t or "parametris" in t),
            ("pagination off-by-one", "page - 1" in t or "page-1" in t or "off-by-one" in t or "(page - 1)" in t),
            ("missing ownership/authorization check on delete", ("authoriz" in t or "ownership" in t or "owner" in t or "permission" in t)),
            ("bare except swallows payment errors", "except" in t and any(k in t for k in ["bare", "swallow", "silent", "hides", "masks", "ignor"]))]


DIRECT = [("sql_revenue", "SQLite revenue report (distinct counts, date bounds, ties)", run_sql),
          ("bash_macos", "macOS bash 3.2 file report script", run_bash),
          ("tool_calling", "Function/tool calling (agent use)", run_tools),
          ("long_context", "~20K-token codebase question answering", run_longctx),
          ("code_review", "Security/bug review of a PR diff", run_review)]


# ------------------------------------------------------------------ main
def record(model, sid, arm, res, log, meta, d):
    passed = sum(ok for _, ok in res) if isinstance(res, list) else res[0]
    total = len(res) if isinstance(res, list) else res[1]
    detail = res if isinstance(res, list) else res[2]
    tokens = sum(r.get("eval_count", 0) for r in log)
    wall = sum(r.get("wall", 0) for r in log)
    (d / "_transcript.json").write_text(json.dumps([{"content": r["message"].get("content"), "tool_calls": r["message"].get("tool_calls"), "eval_count": r.get("eval_count"), "wall": r.get("wall")} for r in log], indent=1))
    row = dict(model=model, scenario=sid, arm=arm, passed=passed, total=total, tokens=tokens, wall=round(wall, 1), **meta,
               failed=[n for n, ok in detail if not ok])
    with open(HERE / "results.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")
    extra = "".join(f" {k}={v}" for k, v in meta.items())
    print(f"{model:16} {sid:20} {arm:19} {passed:>2}/{total:<2} {wall:6.0f}s {tokens:6} tok{extra}", flush=True)


def main(models, only=None):
    for model in models:
        for sc in SCENARIOS:
            if only and sc["id"] not in only:
                continue
            for arm, fn in ARMS.items():
                d = RUNS / model.replace(":", "_") / sc["id"] / arm.replace(" ", "_")
                shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
                log = []
                try:
                    meta = fn(model, sc, d, log)
                    res = grade_hidden(sc, d)
                except Exception as e:
                    meta, res = {"error": str(e)[:100]}, (0, expected_checks(sc), [])
                record(model, sc["id"], arm, res, log, meta, d)
        for sid, _, fn in DIRECT:
            if only and sid not in only:
                continue
            d = RUNS / model.replace(":", "_") / sid
            shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
            log = []
            try:
                res = fn(model, d, log); meta = {}
            except Exception as e:
                res, meta = [("crashed", False)], {"error": str(e)[:100]}
            record(model, sid, "direct", res, log, meta, d)
        unload(model)


if __name__ == "__main__":
    args = sys.argv[1:]
    only = set(a.split("=", 1)[1].split(",")) if any(a.startswith("--only=") for a in args) else None
    models = [a for a in args if not a.startswith("--")] or list(MODELS)
    main(models, only)
