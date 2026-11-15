"""Bearer token issuing and expiry checks."""
from datetime import datetime, timedelta, timezone


def issue_token(user: str, ttl_seconds: int, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    return {"user": user, "expires_at": now + timedelta(seconds=ttl_seconds)}


def is_expired(token: dict) -> bool:
    return token["expires_at"] < datetime.utcnow()


def remaining_seconds(token: dict, now=None) -> float:
    now = now or datetime.now(timezone.utc)
    return max(0.0, (token["expires_at"] - now).total_seconds())
