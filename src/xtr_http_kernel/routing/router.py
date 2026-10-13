"""The application's route table."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .router_interface import RouterInterface

if TYPE_CHECKING:
    from .route_collection import RouteCollection

__all__ = ["Router"]


@final
class Router(RouterInterface):
    """The application's route table, built once and read by name.

    It holds the collection it is given: whoever builds it — the bundle from
    every route loader and routes file, or a test by hand — arranges the routes
    first.
    """

    __slots__ = ("_collection",)

    _collection: RouteCollection

    def __init__(self, collection: RouteCollection) -> None:
        """Hold the arranged route table."""
        self._collection = collection

    @override
    def get_route_collection(self) -> RouteCollection:
        # A copy: the table was mounted as it is, and changing it here would
        # only make the router report routes nothing serves.
        return self._collection.copy()
