import csv, io
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
def _amt(s):
    s = s.strip(); neg = False
    if s.startswith("(") and s.endswith(")"): neg, s = True, s[1:-1]
    if s.startswith("-"): neg, s = not neg, s[1:]
    s = s.replace("$", "").replace(",", "")
    v = Decimal(s)
    return -v if neg else v
def summarize(text):
    lines = text.split("\n"); out = {}; hdr = None
    for n, line in enumerate(lines, 1):
        if not line.strip(): continue
        row = next(csv.reader([line]))
        if hdr is None:
            hdr = {h.strip().lower(): i for i, h in enumerate(row)}; continue
        try: a = _amt(row[hdr["amount"]])
        except (InvalidOperation, IndexError): raise ValueError(f"bad amount on line {n}")
        cat = row[hdr["category"]].strip() or "Uncategorized"
        out[cat] = out.get(cat, Decimal(0)) + a
    return {k: v.quantize(Decimal("0.01"), ROUND_HALF_UP) for k, v in out.items()}
