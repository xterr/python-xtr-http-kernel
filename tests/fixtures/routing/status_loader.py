"""A loader whose endpoints validate a path parameter and ask the container for a service."""

from __future__ import annotations

# Read at runtime: the framework reads the endpoints' annotations.
from xtr_dependency_injection import Injected

from xtr_http_kernel.routing import (
    Route,
    RouteCollection,
    RouterInterface,
)
from xtr_http_kernel.routing.decorator import as_route_loader


async def page(number: int) -> dict[str, int]:
    return {"page": number}


async def status(router: Injected[RouterInterface]) -> dict[str, int]:
    return {"routes": len(router.get_route_collection())}


@as_route_loader("status")
class StatusRouteLoader:
    def load_routes(self) -> RouteCollection:
        routes = RouteCollection()
        routes.add("status_page", Route("/pages/{number}", page, methods=("GET",)))
        routes.add("status", Route("/status", status, methods=("GET",)))
        return routes
