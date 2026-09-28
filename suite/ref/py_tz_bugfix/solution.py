from datetime import datetime, timedelta, timezone
def _utc(d):
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d
def is_active(sub, now=None):
    now = _utc(now) if now else datetime.now(timezone.utc)
    start = _utc(datetime.fromisoformat(sub["started_at"]))
    return bool(start <= now < start + timedelta(days=sub["period_days"]))
