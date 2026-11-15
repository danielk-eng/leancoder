"""User record validation."""
from .rules import is_email, min_length


def validate_user(record, errors=[]):
    """Return a list of human readable problems with `record` (empty if valid)."""
    if not min_length(record.get("name", ""), 2):
        errors.append("name too short")
    if not is_email(record.get("email", "")):
        errors.append("invalid email")
    if record.get("age", 0) < 18:
        errors.append("must be an adult")
    return errors


def is_valid(record) -> bool:
    return not validate_user(record)
