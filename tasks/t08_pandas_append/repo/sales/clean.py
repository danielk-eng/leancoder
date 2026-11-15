"""Row cleaning helpers."""


def normalize(row: dict) -> dict:
    return {"name": str(row["name"]).strip().title(), "qty": int(row["qty"])}
