"""Prove the graders are fair: reference solutions must score 100%, deliberately wrong answers must score low."""
import json, shutil, tempfile
from pathlib import Path
import run_suite as R

HERE = Path(__file__).parent
work = Path(tempfile.mkdtemp(prefix="ollama_bench_validate_"))
ok_all = True


def show(label, res, expect_full):
    global ok_all
    passed, total = (sum(ok for _, ok in res), len(res)) if isinstance(res, list) else res[:2]
    detail = res if isinstance(res, list) else res[2]
    good = (passed == total) if expect_full else (passed < total)
    ok_all &= good
    failed = [n for n, ok in detail if not ok]
    print(f"{'OK ' if good else 'BAD'} {label:34} {passed:>2}/{total:<2} {failed if failed and expect_full else ''}")


print("Reference solutions (must be 100%):")
for sc in R.SCENARIOS:
    d = work / sc["id"]
    shutil.copytree(HERE / "ref" / sc["id"], d)
    show(sc["id"], R.grade_hidden(sc, d), True)

print("\nNegative control (wrong solution must fail):")
d = work / "neg_invoice"; d.mkdir()
(d / "solution.py").write_text("def calc(items, coupon=None, country='US'):\n    return 0.0\n")
show("py_refactor_invoice, returns 0.0", R.grade_hidden([s for s in R.SCENARIOS if s["id"] == "py_refactor_invoice"][0], d), False)

ANSWERS = {
    "sql reference": (R.run_sql, True, "```sql\nSELECT c.name, SUM(oi.qty*oi.unit_cents) AS revenue_cents, COUNT(DISTINCT o.id) AS order_count FROM customers c JOIN orders o ON o.customer_id=c.id JOIN order_items oi ON oi.order_id=o.id WHERE o.status='paid' AND o.created_at >= '2026-09-01' AND o.created_at < '2026-10-01' GROUP BY c.id ORDER BY revenue_cents DESC, c.name ASC LIMIT 3;\n```"),
    "sql wrong (COUNT(*), no dates)": (R.run_sql, False, "```sql\nSELECT c.name, SUM(oi.qty*oi.unit_cents) r, COUNT(*) n FROM customers c JOIN orders o ON o.customer_id=c.id JOIN order_items oi ON oi.order_id=o.id WHERE o.status='paid' GROUP BY c.id ORDER BY r DESC LIMIT 3;\n```"),
    "bash reference": (R.run_bash, True, "```bash\n#!/bin/bash\nif [ $# -lt 3 ]; then echo 'usage: report.sh DIR DAYS MB' >&2; exit 2; fi\nmin=$(( $3 * 1048576 ))\nfind \"$1\" -type f -mtime +\"$2\" -print0 | while IFS= read -r -d '' f; do s=$(stat -f %z \"$f\"); [ \"$s\" -gt \"$min\" ] && printf '%s\\t%s\\n' \"$s\" \"$f\"; done | sort -t$'\\t' -k1,1nr\n```"),
    "long-context reference": (R.run_longctx, True, json.dumps({"timeout_ms": 12000, "timeout_file": "app/config/production.py", "retries": 5, "receipt_caller": "finalize_order"})),
    "long-context decoy answers": (R.run_longctx, False, json.dumps({"timeout_ms": 7300, "timeout_file": "app/config/base.py", "retries": 3, "receipt_caller": "refund_order"})),
}
print("\nDirect graders (fake model answers):")
cur = {}
R.chat = lambda model, msgs, tools=None, num_ctx=32768: {"message": {"content": cur["a"]}, "prompt_eval_count": 0}
for label, (fn, full, answer) in ANSWERS.items():
    cur["a"] = answer
    d = work / label.replace(" ", "_"); d.mkdir()
    show(label, fn("x", d, []), full)

shutil.rmtree(work)
print("\nALL GRADERS VALID" if ok_all else "\nGRADER PROBLEM FOUND")
