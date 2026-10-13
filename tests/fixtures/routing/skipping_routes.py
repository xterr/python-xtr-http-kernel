"""An application serving none of the books routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from xtr_http_kernel.routing.loader.configurator import RoutingConfigurator


@as_routes
def no_books(routes: RoutingConfigurator) -> None:
    routes.skip("books")
