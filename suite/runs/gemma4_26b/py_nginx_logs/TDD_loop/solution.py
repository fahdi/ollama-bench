import re
from datetime import datetime
from collections import Counter
from typing import Any

# Regex to capture the main components of the combined log format:
# 1: IP, 2: remote_user, 3: time, 4: request, 5: status, 6: bytes, 7: referer, 8: user_agent
LOG_PATTERN = re.compile(
    r'^(\S+) \S+ (\S+) \[(.*?)\] "(.*?)" (\S+) (\S+) "(.*?)" "(.*?)"$'
)

def parse_line(line: str) -> dict[str, Any] | None:
    if not line.strip():
        return None

    match = LOG_PATTERN.match(line)
    if not match:
        return None

    ip, _, time_str, request_str, status_str, bytes_str, _, _ = match.groups()

    # 1. Parse Timestamp
    # Format: 10/Oct/2026:13:55:36 +0000
    try:
        dt = datetime.strptime(time_str, "%d/%b/%Y:%H:%M:%S %z")
    except ValueError:
        return None

    # 2. Parse Request (METHOD PATH PROTOCOL)
    request_parts = request_str.split()
    if len(request_parts) != 3:
        return None
    
    method, full_path, protocol = request_parts

    # 3. Parse Status
    try:
        status = int(status_str)
    except ValueError:
        return None

    # 4. Parse Bytes
    try:
        bytes_val = 0 if bytes_str == "-" else int(bytes_str)
    except ValueError:
        return None

    # 5. Strip Query String from Path
    path = full_path.split('?', 1)[0]

    return {
        "ip": ip,
        "time": dt,
        "method": method,
        "path": path,
        "status": status,
        "bytes": bytes_val
    }

def top_error_paths(lines: iter[str], n: int = 3) -> list[tuple[str, int]]:
    counts = Counter()
    
    for line in lines:
        data = parse_line(line)
        if data and data["status"] >= 500:
            counts[data["path"]] += 1
            
    # Sort by count descending, then path ascending
    # We use -x[1] for descending count and x[0] for ascending path
    sorted_items = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    
    return sorted_items[:n]
