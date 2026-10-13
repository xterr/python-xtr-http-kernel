"""An application arranging the books routes and adding one of its own."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from xtr_http_kernel.routing.loader.configurator import RoutingConfigurator


async def home() -> dict[str, str]:
    return {"home": "page"}


@as_routes
def shop(routes: RoutingConfigurator) -> None:
    _ = routes.import_("books").prefix("/shop").name_prefix("shop_").exclude("books_show")
    _ = routes.add("home", "/").endpoint(home).methods("GET")
