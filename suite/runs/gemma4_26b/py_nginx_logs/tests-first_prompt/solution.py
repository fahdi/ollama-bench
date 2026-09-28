import re
from datetime import datetime
from collections import Counter

# Regex for Nginx Combined Log Format
# 1: IP, 2: Remote User, 3: Time, 4: Request, 5: Status, 6: Bytes, 7: Referer, 8: User Agent
LOG_PATTERN = re.compile(
    r'^(\S+) \S+ (\S+) \[(.*?)\] "(.*?)" (\d{3}) (\d+|-|(?:\s)) "(.*?)" "(.*?)"$'
)

def parse_line(line: str) -> dict | None:
    """Parses a single nginx combined log line."""
    if not line or not line.strip():
        return None

    match = LOG_PATTERN.match(line.strip())
    if not match:
        return None

    ip, remote_user, time_str, request, status_str, bytes_str, referer, user_agent = match.groups()

    # 1. Parse Timestamp
    # Format: 10/Oct/2026:13:55:36 +0000
    try:
        dt = datetime.strptime(time_str, "%d/%b/%Y:%H:%M:%S %z")
    except ValueError:
        return None

    # 2. Parse Request (METHOD PATH PROTOCOL)
    req_parts = request.split()
    if len(req_parts) != 3:
        return None
    
    method, full_path, protocol = req_parts

    # 3. Parse Path (strip query string)
    path = full_path.split('?', 1)[0]

    # 4. Parse Status
    try:
        status = int(status_str)
    except ValueError:
        return None

    # 5. Parse Bytes
    try:
        if bytes_str == "-":
            bytes_val = 0
        else:
            bytes_val = int(bytes_str)
    except ValueError:
        return None

    return {
        "ip": ip,
        "time": dt,
        "method": method,
        "path": path,
        "status": status,
        "bytes": bytes_val
    }

def top_error_paths(lines, n: int = 3) -> list[tuple[str, int]]:
    """Returns the top n paths with status >= 500."""
    counts = Counter()
    
    for line in lines:
        data = parse_line(line)
        if data and data["status"] >= 500:
            counts[data["path"]] += 1
            
    # Sort by count descending, then path ascending
    # Python's sort is stable. We sort by path first, then by count.
    sorted_paths = sorted(counts.items(), key=lambda x: x[0])
    sorted_paths.sort(key=lambda x: x[1], reverse=True)
    
    return sorted_paths[:n]
