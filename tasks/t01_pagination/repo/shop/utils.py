"""Small string helpers used across the shop."""
import re


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def format_price(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def truncate(text: str, limit: int = 40) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
