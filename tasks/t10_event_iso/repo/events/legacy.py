"""Legacy exporters kept for old dashboards."""
from datetime import datetime


def legacy_label(ts: float) -> str:
    return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
