"""Turn seconds into short human strings."""


def humanize(seconds: int) -> str:
    parts = []
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60), ("s", 1)):
        qty, seconds = divmod(seconds, size)
        if qty:
            parts.append(f"{qty}{unit}")
    return "".join(parts) or "0s"
