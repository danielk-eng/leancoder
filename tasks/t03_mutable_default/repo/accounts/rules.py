"""Reusable validation predicates."""
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)


def is_email(value: str) -> bool:
    return bool(EMAIL_RE.match(value or ""))


def min_length(value: str, n: int) -> bool:
    return len(value or "") >= n
