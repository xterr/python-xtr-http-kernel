"""An application trying to move routes a standard fixes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from xtr_http_kernel.routing.loader.configurator import RoutingConfigurator


@as_routes
def moved(routes: RoutingConfigurator) -> None:
    _ = routes.import_("well_known").prefix("/api")
