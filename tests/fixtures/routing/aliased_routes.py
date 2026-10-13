"""An application giving a contributed route a second name."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from xtr_http_kernel.routing.loader.configurator import RoutingConfigurator


@as_routes
def catalogue(routes: RoutingConfigurator) -> None:
    _ = routes.import_("books")
    _ = routes.alias("catalogue", "books_list")
