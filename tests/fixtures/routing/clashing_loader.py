"""A second resource contributing a route named like one of the books resource."""

from __future__ import annotations

from tests.fixtures.routing.loaders import list_books
from xtr_http_kernel.routing import Route, RouteCollection
from xtr_http_kernel.routing.decorator import as_route_loader


@as_route_loader("library")
class LibraryRouteLoader:
    def load_routes(self) -> RouteCollection:
        routes = RouteCollection()
        routes.add("books_list", Route("/library", list_books, methods=("GET",)))
        return routes
