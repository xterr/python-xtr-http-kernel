"""What a class declared with ``@as_route_loader`` provides."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .route_collection import RouteCollection

__all__ = ["RouteLoaderInterface"]


@runtime_checkable
class RouteLoaderInterface(Protocol):
    """What a class declared with ``@as_route_loader`` provides: its routes.

    A loader is built with no arguments while the kernel compiles, before any
    service exists: what it contributes is fixed by the code that ships it. A
    route a deployment turns off keeps answering — its endpoint refuses — and
    an application that wants it gone leaves it out in a routes file.
    """

    def load_routes(self) -> RouteCollection:
        """Return the routes this loader contributes, at their default paths and names."""
        ...
