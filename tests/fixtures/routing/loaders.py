"""Two route resources, as a bundle would ship them."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_route_resource

if TYPE_CHECKING:
    from fastapi import APIRouter


@as_route_resource("books")
def books_routes(router: APIRouter) -> None:
    """Fill the router with the books endpoints."""

    @router.get("/books", name="books_list")
    async def list_books() -> dict[str, str]:
        return {"books": "all"}

    @router.get("/books/{book_id}", name="books_show")
    async def show_book(book_id: str) -> dict[str, str]:
        return {"book": book_id}


@as_route_resource("well_known")
def well_known_routes(router: APIRouter) -> None:
    """Fill the router with the document a standard places."""

    @router.get("/.well-known/metadata", name="metadata")
    async def describe() -> dict[str, str]:
        return {"issuer": "here"}
