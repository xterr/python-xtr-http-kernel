"""A loader contributing a different path each time it is asked, and a route reporting it."""

from __future__ import annotations

import itertools

# Read at runtime: the framework reads the endpoint's annotations.
from xtr_dependency_injection import Injected

from xtr_http_kernel.routing import Route, RouteCollection, RouterInterface
from xtr_http_kernel.routing.decorator import as_route_loader

_VERSIONS = itertools.count(1)


async def changing() -> dict[str, str]:
    return {}


async def table(router: Injected[RouterInterface]) -> dict[str, str]:
    routes = router.get_route_collection()
    return {name: route.path for name, route in routes if name == "changing"}


@as_route_loader("changing")
class ChangingRouteLoader:
    def load_routes(self) -> RouteCollection:
        routes = RouteCollection()
        routes.add("changing", Route(f"/v{next(_VERSIONS)}", changing, methods=("GET",)))
        routes.add("table", Route("/table", table, methods=("GET",)))
        return routes
