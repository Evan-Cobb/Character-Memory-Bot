"""Shared text-input validation, with no Discord dependency."""


def text(value: str, label: str, limit: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text.")
    value = value.strip()
    if not value or len(value) > limit:
        raise ValueError(f"{label} must contain 1 to {limit} characters.")
    return value
