"""What a deprecated alias tells whoever still uses it."""

from __future__ import annotations

from typing import TypedDict

__all__ = ["AliasDeprecation"]


class AliasDeprecation(TypedDict):
    """The package and version that deprecated an alias, and the message to show.

    Attributes:
        package: The package that deprecated the alias.
        version: The version it was deprecated in.
        message: The message, with the alias's name filled in.
    """

    package: str
    version: str
    message: str
