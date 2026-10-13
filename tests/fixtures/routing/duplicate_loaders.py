"""A second loader claiming a resource the fixture loaders already provide."""

from __future__ import annotations

from xtr_http_kernel.routing import RouteCollection
from xtr_http_kernel.routing.decorator import as_route_loader


@as_route_loader("books")
class OtherBooksRouteLoader:
    def load_routes(self) -> RouteCollection:
        return RouteCollection()
