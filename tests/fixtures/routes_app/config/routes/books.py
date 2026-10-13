"""The routes file a bundle's recipe would write: the books routes under /shop."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from xtr_http_kernel.routing.loader.configurator import RoutingConfigurator


@as_routes
def books(routes: RoutingConfigurator) -> None:
    _ = routes.import_("books").prefix("/shop")
