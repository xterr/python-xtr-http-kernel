"""A second function contributing the books resource, claiming a name it already holds.

Several functions may fill one resource; what may not is two routes of it
under one name — refused while staging, whether or not anything includes it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_route_resource

if TYPE_CHECKING:
    from fastapi import APIRouter


@as_route_resource("books")
def other_books_routes(router: APIRouter) -> None:
    """Fill the router with a second route named books_list."""

    @router.get("/other", name="books_list")
    async def other_list() -> dict[str, str]:
        return {"books": "other"}
