"""What reads the application's whole route table."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .route_collection import RouteCollection

__all__ = ["RouterInterface"]


@runtime_checkable
class RouterInterface(Protocol):
    """What reads the application's whole route table."""

    def get_route_collection(self) -> RouteCollection:
        """Return every route the application serves, as the routes files arranged them.

        The collection returned is the caller's own: changing it changes nothing
        that is served.
        """
        ...
