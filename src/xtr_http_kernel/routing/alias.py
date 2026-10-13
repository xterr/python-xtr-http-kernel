"""Another name for a route, which may be on its way out."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Final, Self, final

from .exception.invalid_argument_error import InvalidArgumentError

if TYPE_CHECKING:
    from .alias_deprecation import AliasDeprecation

__all__ = ["Alias"]

_PLACEHOLDER: Final[str] = "%alias_id%"
_DEFAULT_MESSAGE: Final[str] = (
    'The "%alias_id%" route alias is deprecated. '
    "You should stop using it, as it will be removed in the future."
)
_FORBIDDEN: Final[tuple[str, ...]] = ("\r", "\n", "*/")


@final
class Alias:
    """Another name for a route, resolved when the route is looked up.

    It is mutable on purpose: :meth:`RouteCollection.add_alias` hands back the
    alias it stored, so a caller can mark that very alias deprecated.
    """

    __slots__ = ("_deprecation", "_id")

    _id: str
    _deprecation: AliasDeprecation | None

    def __init__(self, target: str) -> None:
        """Name the route (or alias) this alias stands for."""
        self._id = target
        self._deprecation = None

    @property
    def id(self) -> str:
        """The name of the route (or alias) this alias stands for."""
        return self._id

    def with_id(self, target: str) -> Alias:
        """Return a copy standing for another name, its deprecation kept."""
        other: Alias = copy.copy(self)
        other._id = target
        return other

    def set_deprecated(self, package: str, version: str, message: str = "") -> Self:
        """Mark the alias deprecated.

        Args:
            package: The package deprecating it.
            version: The version deprecating it.
            message: What to tell its users; ``%alias_id%`` stands for the
                alias's name. Left empty, a standard message is used.

        Raises:
            InvalidArgumentError: The message spans lines, contains ``*/``, or
                does not name the alias.
        """
        if message:
            if any(part in message for part in _FORBIDDEN):
                raise InvalidArgumentError(
                    "Invalid characters found in deprecation template: "
                    'it must not contain "\\r", "\\n" or "*/".'
                )
            if _PLACEHOLDER not in message:
                raise InvalidArgumentError(
                    f'The deprecation template must contain the "{_PLACEHOLDER}" placeholder.'
                )
        self._deprecation = {
            "package": package,
            "version": version,
            "message": message or _DEFAULT_MESSAGE,
        }
        return self

    def is_deprecated(self) -> bool:
        """Tell whether the alias is marked deprecated."""
        return self._deprecation is not None

    def get_deprecation(self, name: str) -> AliasDeprecation | None:
        """Return the deprecation with ``name`` filled in, or ``None`` when not deprecated."""
        if self._deprecation is None:
            return None
        return {
            "package": self._deprecation["package"],
            "version": self._deprecation["version"],
            "message": self._deprecation["message"].replace(_PLACEHOLDER, name),
        }
