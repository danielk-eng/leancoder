"""Legacy session helpers (naive UTC timestamps)."""
from datetime import datetime


def session_started() -> datetime:
    return datetime.utcnow()


def session_age_seconds(started: datetime) -> float:
    return (datetime.utcnow() - started).total_seconds()
