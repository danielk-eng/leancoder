"""Timestamp formatting for the public events API."""
from datetime import datetime


def to_iso(ts: float) -> str:
    """Epoch seconds -> ISO-8601 string in UTC, with explicit offset."""
    return datetime.utcfromtimestamp(ts).isoformat()


def day_bucket(ts: float) -> str:
    return to_iso(ts)[:10]
