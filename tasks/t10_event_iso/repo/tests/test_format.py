from events.format import day_bucket, to_iso


def test_iso_has_offset():
    assert to_iso(1704067200) == "2024-01-01T00:00:00+00:00"


def test_fractional_seconds():
    assert to_iso(1704067200.5) == "2024-01-01T00:00:00.500000+00:00"


def test_bucket():
    assert day_bucket(1704067200) == "2024-01-01"
