"""A resource whose endpoints validate a path parameter and ask the container for a value."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

# Read at runtime: the framework reads the endpoints' annotations.
from xtr_dependency_injection import Autowire

from xtr_http_kernel.routing.decorator import as_route_resource

if TYPE_CHECKING:
    from fastapi import APIRouter


@as_route_resource("status")
def status_routes(router: APIRouter) -> None:
    """Fill the router with the status endpoints."""

    @router.get("/pages/{number}", name="status_page")
    async def page(number: int) -> dict[str, int]:
        return {"page": number}

    @router.get("/status", name="status")
    async def status(env: Annotated[str, Autowire(param="kernel.environment")]) -> dict[str, str]:
        return {"env": env}
