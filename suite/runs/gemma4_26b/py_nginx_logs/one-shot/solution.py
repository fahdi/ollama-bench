import re
from datetime import datetime
from collections import Counter
from urllib.parse import urlparse

# Regex for Nginx Combined Log Format
# 1: IP, 2: Remote User, 3: User, 4: Timestamp, 5: Request, 6: Status, 7: Bytes, 8: Referer, 9: User Agent
LOG_PATTERN = re.compile(
    r'^(\S+) (\S+) (\S+) \[(.*?)\] "(.*?)" (\d{3}) (\d+|-| ) "(.*?)" "(.*?)"$'
)

def parse_line(line: str) -> dict | None:
    """
    Parses a single line of Nginx combined log format.
    Returns a dict or None if the line is malformed.
    """
    if not line or not line.strip():
        return None

    match = LOG_PATTERN.match(line.strip())
    if not match:
        return None

    try:
        ip = match.group(1)
        timestamp_str = match.group(4)
        request_str = match.group(5)
        status_str = match.group(6)
        bytes_str = match.group(7)

        # 1. Parse Timestamp: [10/Oct/2026:13:55:36 +0000]
        # Format: %d/%b/%Y:%H:%M:%S %z
        dt = datetime.strptime(timestamp_str, "%d/%b/%Y:%H:%M:%S %z")

        # 2. Parse Request: "METHOD PATH PROTOCOL"
        req_parts = request_str.split()
        if len(req_parts) != 3:
            return None
        method, full_path, protocol = req_parts

        # 3. Parse Path (strip query string)
        path = urlparse(full_path).path

        # 4. Parse Status
        status = int(status_str)

        # 5. Parse Bytes
        if bytes_str == "-" or bytes_str.strip() == "":
            bytes_val = 0
        else:
            bytes_val = int(bytes_str)

        return {
            "ip": ip,
            "time": dt,
            "method": method,
            "path": path,
            "status": status,
            "bytes": bytes_val
        }

    except (ValueError, IndexError, AttributeError):
        # Catches bad date formats, non-int status/bytes, or split errors
        return None

def top_error_paths(lines, n: int = 3) -> list[tuple[str, int]]:
    """
    Counts responses with status >= 500 per path.
    Returns top n as (path, count) sorted by count DESC, then path ASC.
    """
    counts = Counter()
    
    for line in lines:
        data = parse_line(line)
        if data and data["status"] >= 500:
            counts[data["path"]] += 1
            
    # Sort by count descending (-x[1]), then path ascending (x[0])
    sorted_paths = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    
    return sorted_paths[:n]
