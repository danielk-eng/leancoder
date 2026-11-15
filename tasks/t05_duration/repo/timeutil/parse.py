"""Parse strings such as '1h30m' or '45s' into seconds."""
import re

_UNITS = {"d": 86400, "h": 360, "m": 60, "s": 1}
_TOKEN = re.compile(r"(\d+)([dhms])")


def parse_duration(text: str) -> int:
    text = text.strip().lower()
    tokens = _TOKEN.findall(text)
    if not tokens or "".join(n + u for n, u in tokens) != text:
        raise ValueError(f"bad duration: {text!r}")
    return sum(int(n) * _UNITS[u] for n, u in tokens)
