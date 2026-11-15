import pytest
from settings.access import get_nested, require

CFG = {"db": {"port": 0, "name": "x", "debug": False}, "title": "hi"}


def test_existing_values():
    assert get_nested(CFG, "db.name") == "x"


def test_falsy_values_are_returned():
    assert get_nested(CFG, "db.port", 5432) == 0
    assert get_nested(CFG, "db.debug", True) is False


def test_missing_returns_default():
    assert get_nested(CFG, "db.user", "root") == "root"
    assert get_nested(CFG, "cache.ttl") is None


def test_non_dict_intermediate_returns_default():
    assert get_nested(CFG, "title.length", -1) == -1


def test_require_raises():
    with pytest.raises(KeyError):
        require(CFG, "db.user")
