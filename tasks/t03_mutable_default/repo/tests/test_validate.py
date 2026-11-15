from accounts.validate import validate_user, is_valid

GOOD = {"name": "Ann", "email": "ann@example.com", "age": 30}
BAD = {"name": "A", "email": "nope", "age": 3}


def test_bad_user_reports_all_problems():
    assert validate_user(BAD) == ["name too short", "invalid email", "must be an adult"]


def test_errors_do_not_leak_between_calls():
    validate_user(BAD)
    assert validate_user(GOOD) == []


def test_is_valid():
    validate_user(BAD)
    assert is_valid(GOOD)
