"""Route resources of every shape: a plain function, an injected service, two groups."""

from __future__ import annotations

from typing import TYPE_CHECKING

# Read at runtime: the framework reads the endpoint's annotations.
from xtr_dependency_injection import Injected

from tests.support.bundles import (
    TickController,  # noqa: TC001 -- the framework reads this annotation
)
from xtr_http_kernel.routing.decorator import as_route_resource

if TYPE_CHECKING:
    from fastapi import APIRouter


@as_route_resource("pings")
def ping_routes(router: APIRouter) -> None:
    """Fill the router with the proof a declared route is served."""

    @router.get("/ping", name="ping")
    async def ping() -> dict[str, str]:
        return {"ping": "pong"}


@as_route_resource("ticks")
def tick_routes(router: APIRouter) -> None:
    """Fill the router with the endpoint injecting its controller."""

    @router.get("/ticks/{number}", name="tick_show")
    async def show(number: int, controller: Injected[TickController]) -> dict[str, object]:
        """Answer with the number in the path and this request's tick token."""
        return {"number": number, "tick": controller.token}


@as_route_resource("books_declared")
def declared_books_routes(router: APIRouter) -> None:
    """Fill the router with a resource of its own."""

    @router.get("/books", name="declared_books_list")
    async def list_books() -> dict[str, str]:
        return {"books": "declared"}


@as_route_resource("shop")
def shop_routes(router: APIRouter) -> None:
    """Fill the router with a group under its own prefix."""

    @router.get("/shop/items", name="shop_items")
    async def items() -> dict[str, str]:
        return {"items": "many"}
