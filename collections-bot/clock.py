"""Injectable date source: PTP suppression compares ISO dates in bank-local time."""
from datetime import datetime
from zoneinfo import ZoneInfo


def kl_today() -> str:
    return datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).date().isoformat()
