"""What a profile never keeps the value of: credentials, by header or by field name."""

from __future__ import annotations

from typing import Final

__all__ = ["MASK", "is_sensitive_field", "is_sensitive_header", "masked_field", "masked_header"]

MASK: Final = "******"

_SENSITIVE_HEADERS: Final = frozenset(
    {"authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key"}
)
_SENSITIVE_FIELDS: Final = ("password", "secret", "token", "passwd", "api_key", "apikey")


def is_sensitive_header(name: str) -> bool:
    """Tell whether a header with this name carries a credential."""
    return name.lower() in _SENSITIVE_HEADERS


def is_sensitive_field(name: str) -> bool:
    """Tell whether a field, parameter or cookie with this name likely holds a credential."""
    lowered = name.lower()
    return any(word in lowered for word in _SENSITIVE_FIELDS)


def masked_header(name: str, value: str) -> str:
    """Return ``value``, or the mask when the header carries a credential."""
    return MASK if is_sensitive_header(name) else value


def masked_field(name: str, value: str) -> str:
    """Return ``value``, or the mask when the field likely holds a credential."""
    return MASK if is_sensitive_field(name) else value
