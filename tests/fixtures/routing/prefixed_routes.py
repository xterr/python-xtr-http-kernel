"""An application putting the books routes under /api."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from xtr_http_kernel.routing.loader.configurator import RoutingConfigurator


@as_routes
def api(routes: RoutingConfigurator) -> None:
    _ = routes.import_("books").prefix("/api")
