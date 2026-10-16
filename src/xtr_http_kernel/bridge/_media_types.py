"""Which content types have a parsed side.

One rule, read in two places: the eager factory parses a body per it, and the
served request materialises — at the seam the container hands the message on
— only the bodies this rule can parse, leaving a body with no parsed side to
whoever reads it.
"""

from __future__ import annotations

from typing import Final

__all__ = ["has_parsed_side", "is_form", "is_json", "media_type_of"]

_FORM_MEDIA_TYPES: Final = frozenset({"application/x-www-form-urlencoded", "multipart/form-data"})
_JSON_MEDIA_TYPES: Final = frozenset({"application/json", "application/x-json"})
_JSON_SUFFIX: Final = "+json"


def media_type_of(content_type: str) -> str:
    """Return the media type a ``Content-Type`` header names, without its parameters."""
    return content_type.partition(";")[0].strip().lower()


def is_form(media_type: str) -> bool:
    """Tell whether a media type says the body is a submitted form."""
    return media_type in _FORM_MEDIA_TYPES


def is_json(media_type: str) -> bool:
    """Tell whether a media type says the body is JSON, suffixed types included."""
    return media_type in _JSON_MEDIA_TYPES or media_type.endswith(_JSON_SUFFIX)


def has_parsed_side(content_type: str) -> bool:
    """Tell whether a body under this ``Content-Type`` has a parsed side to answer for."""
    media_type = media_type_of(content_type)
    return is_form(media_type) or is_json(media_type)
