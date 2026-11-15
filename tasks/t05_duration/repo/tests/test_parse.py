import pytest
from timeutil.parse import parse_duration
from timeutil.humanize import humanize


def test_mixed():
    assert parse_duration("1h30m") == 5400


def test_simple_units():
    assert parse_duration("45s") == 45
    assert parse_duration("2h") == 7200
    assert parse_duration("1d") == 86400


def test_invalid():
    with pytest.raises(ValueError):
        parse_duration("soon")


def test_roundtrip():
    assert parse_duration(humanize(98765)) == 98765
