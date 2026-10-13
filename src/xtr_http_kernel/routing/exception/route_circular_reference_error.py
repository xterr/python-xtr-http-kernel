"""A chain of aliases leads back to a name it already passed."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .routing_error import RoutingError

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["RouteCircularReferenceError"]


class RouteCircularReferenceError(RoutingError):
    """A chain of aliases leads back to a name it already passed.

    Attributes:
        name: The name the loop starts and ends at.
        path: The names followed, the first one repeated at the end.
    """

    name: str
    path: tuple[str, ...]

    def __init__(self, name: str, path: Sequence[str]) -> None:
        """Record where the loop starts and the names it went through."""
        self.name = name
        self.path = tuple(path)
        super().__init__(
            f'Circular reference detected for route "{name}", path: "{" -> ".join(self.path)}".'
        )
