"""Declaring a function as one of the application's routes files.

An application arranges its routes in ``config/routes/*.py``::

    @as_routes
    def oauth2_server(routes: RoutingConfigurator) -> None:
        routes.import_("oauth2_server").prefix("/auth")

Every function so declared, in a module the kernel scans, is called when the
route table is built, in scan order.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, TypeAlias, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_http_kernel.routing.loader.configurator.routing_configurator import (
        RoutingConfigurator,
    )

__all__ = ["ROUTES_ATTRIBUTE", "RoutesFile", "as_routes", "routes_files_of"]

#: Where the declaration is kept on the function.
ROUTES_ATTRIBUTE: Final = "__xtr_routes__"

RoutesFile: TypeAlias = "Callable[[RoutingConfigurator], None]"


def as_routes(target: RoutesFile, /) -> RoutesFile:
    """Declare ``target`` as a routes file: it receives the configurator and arranges routes."""
    setattr(target, ROUTES_ATTRIBUTE, True)
    return target


def routes_files_of(obj: object) -> tuple[RoutesFile, ...]:
    """Return ``obj`` itself when it was declared a routes file, else nothing."""
    if not callable(obj) or isinstance(obj, type):
        return ()
    declared = getattr(obj, "__dict__", {}).get(ROUTES_ATTRIBUTE) is True
    # Only as_routes writes the attribute, on a function typed as a routes file.
    return (cast("RoutesFile", obj),) if declared else ()
