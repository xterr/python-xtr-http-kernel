"""A resource contributing a route at the same method and path as the books resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_route_resource

if TYPE_CHECKING:
    from fastapi import APIRouter


@as_route_resource("shelf")
def shelf_routes(router: APIRouter) -> None:
    """Fill the router with a route answering where books_list answers."""

    @router.get("/books", name="shelf_list")
    async def shelf_list() -> dict[str, str]:
        return {"books": "all"}
