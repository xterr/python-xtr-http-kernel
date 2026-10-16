"""A second resource contributing a route named like one of the books resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_route_resource

if TYPE_CHECKING:
    from fastapi import APIRouter


@as_route_resource("library")
def library_routes(router: APIRouter) -> None:
    """Fill the router with a route claiming the books resource's name."""

    @router.get("/library", name="books_list")
    async def library_list() -> dict[str, str]:
        return {"books": "all"}
