import re
from collections import Counter
from datetime import datetime
RX = re.compile(r'^(\S+) \S+ \S+ \[([^\]]+)\] "([^"]*)" (\S+) (\S+) "[^"]*" "[^"]*"$')
def parse_line(line):
    m = RX.match(line or "")
    if not m: return None
    ip, ts, req, st, by = m.groups()
    parts = req.split()
    if len(parts) != 3 or not st.isdigit(): return None
    try: t = datetime.strptime(ts, "%d/%b/%Y:%H:%M:%S %z")
    except ValueError: return None
    if by != "-" and not by.isdigit(): return None
    return {"ip": ip, "time": t, "method": parts[0], "path": parts[1].split("?")[0], "status": int(st), "bytes": 0 if by == "-" else int(by)}
def top_error_paths(lines, n=3):
    c = Counter(r["path"] for r in map(parse_line, lines) if r and r["status"] >= 500)
    return sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:n]
