"""Two route loaders, as a bundle would ship them."""

from __future__ import annotations

from xtr_http_kernel.routing import Route, RouteCollection
from xtr_http_kernel.routing.decorator import as_route_loader


async def list_books() -> dict[str, str]:
    return {"books": "all"}


async def show_book() -> dict[str, str]:
    return {"book": "one"}


async def describe() -> dict[str, str]:
    return {"issuer": "here"}


@as_route_loader("books")
class BooksRouteLoader:
    def load_routes(self) -> RouteCollection:
        routes = RouteCollection()
        routes.add("books_list", Route("/books", list_books, methods=("GET",)))
        routes.add("books_show", Route("/books/{book_id}", show_book, methods=("GET",)))
        return routes


@as_route_loader("well_known", prefixable=False)
class WellKnownRouteLoader:
    def load_routes(self) -> RouteCollection:
        routes = RouteCollection()
        routes.add("metadata", Route("/.well-known/metadata", describe, methods=("GET",)))
        return routes
