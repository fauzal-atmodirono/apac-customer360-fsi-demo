"""Promise-to-pay helpers: pure functions, no I/O.

A PTP suppresses outbound reminders while ACTIVE and not yet past due; the
stores lazily flip past-due ACTIVE records to BROKEN on read (no scheduler).
Status lifecycle: ACTIVE -> KEPT | CANCELLED (manual) or -> BROKEN (lazy).
"""
from datetime import date, timedelta

PTP_STATUSES = ("ACTIVE", "KEPT", "BROKEN", "CANCELLED")
DEFAULT_PTP_OFFSET_DAYS = 3  # AGREE without an explicit date -> promise in 3 days


def parse_ptp_fields(parsed: dict) -> tuple[str | None, float | None]:
    """Tolerantly pull (ptp_date, ptp_amount) out of the LLM's JSON reply."""
    ptp_date = None
    raw_date = parsed.get("ptp_date")
    if isinstance(raw_date, str):
        try:
            ptp_date = date.fromisoformat(raw_date.strip()).isoformat()
        except ValueError:
            ptp_date = None
    amount = None
    raw_amount = parsed.get("ptp_amount")
    if raw_amount is not None:
        try:
            amount = float(raw_amount)
        except (TypeError, ValueError):
            amount = None
    return ptp_date, amount


def default_promise_date(today: str) -> str:
    return (date.fromisoformat(today) + timedelta(days=DEFAULT_PTP_OFFSET_DAYS)).isoformat()


def normalize_future_date(iso: str | None, today: str) -> str | None:
    """Roll a bare/relative promise date to its next future occurrence.

    The LLM never knows today's date, so "24 Julai" can come back with the wrong
    year — a past year makes the promise instantly BROKEN; a future one locks
    sends forever. A promise is always forward-looking, so any date before today
    is bumped year-by-year until it lands on or after today (the promise day
    itself still counts). Non-ISO input is returned untouched (nothing to fix).
    """
    try:
        d = date.fromisoformat(iso)
        t = date.fromisoformat(today)
    except (ValueError, TypeError):
        return iso
    while d < t:
        try:
            d = d.replace(year=d.year + 1)
        except ValueError:  # 29 Feb -> non-leap year: clamp to 28 Feb
            d = d.replace(year=d.year + 1, day=28)
    return d.isoformat()


def is_suppressed(ptp_record: dict | None, today: str) -> bool:
    """True while an ACTIVE promise is not yet past due (the whole promise day counts)."""
    if not ptp_record:
        return False
    return ptp_record.get("status") == "ACTIVE" and (ptp_record.get("promise_date") or "") >= today
