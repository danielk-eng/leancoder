from datetime import datetime, timedelta, timezone

from auth.tokens import is_expired, issue_token, remaining_seconds


def test_fresh_token_not_expired():
    assert is_expired(issue_token("ann", 60)) is False


def test_old_token_expired():
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    assert is_expired(issue_token("ann", 60, now=past)) is True


def test_remaining():
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert remaining_seconds(issue_token("ann", 90, now=now), now=now) == 90
