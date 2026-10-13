"""A route loader whose load_routes is a coroutine function."""

from __future__ import annotations

from xtr_http_kernel.routing import RouteCollection
from xtr_http_kernel.routing.decorator import as_route_loader


@as_route_loader("async_routes")
class AsyncRouteLoader:
    async def load_routes(self) -> RouteCollection:
        return RouteCollection()
