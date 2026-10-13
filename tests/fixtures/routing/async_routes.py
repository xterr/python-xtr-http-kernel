"""A routes file written as a coroutine function."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from xtr_http_kernel.routing.decorator import RoutesFile, as_routes

if TYPE_CHECKING:
    from xtr_http_kernel.routing.loader.configurator import RoutingConfigurator


async def _shop(routes: RoutingConfigurator) -> None:
    _ = routes.import_("books")


# The decorator's type refuses a coroutine function; the cast stands in for an
# application that wrote one anyway, which the build must still refuse.
shop = as_routes(cast("RoutesFile", _shop))
