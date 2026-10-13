"""A resource contributing a route at the same method and path as the books resource."""

from __future__ import annotations

from tests.fixtures.routing.loaders import list_books
from xtr_http_kernel.routing import Route, RouteCollection
from xtr_http_kernel.routing.decorator import as_route_loader


@as_route_loader("shelf")
class ShelfRouteLoader:
    def load_routes(self) -> RouteCollection:
        routes = RouteCollection()
        routes.add("shelf_list", Route("/books", list_books, methods=("GET",)))
        return routes
