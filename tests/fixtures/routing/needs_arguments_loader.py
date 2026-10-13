"""A route loader asking for a constructor argument, which nothing can give it."""

from __future__ import annotations

from xtr_http_kernel.routing import RouteCollection
from xtr_http_kernel.routing.decorator import as_route_loader


@as_route_loader("needs_arguments")
class NeedsArgumentsRouteLoader:
    prefix: str

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix

    def load_routes(self) -> RouteCollection:
        return RouteCollection()
