"""Building the application's route table while the kernel compiles."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_dependency_injection import CompilerPassInterface

from xtr_http_kernel.routing.exception.invalid_argument_error import InvalidArgumentError
from xtr_http_kernel.routing.loader.routes_file_loader import RoutesFileLoader
from xtr_http_kernel.routing.route_collection import RouteCollection
from xtr_http_kernel.routing.route_table_parameter import ROUTE_TABLE_PARAMETER

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_dependency_injection import ContainerBuilder

    from xtr_http_kernel.routing.decorator.as_routes import RoutesFile
    from xtr_http_kernel.routing.decorator.route_loader_marker import RouteLoaderMarker
    from xtr_http_kernel.routing.route_loader_interface import RouteLoaderInterface

__all__ = ["ROUTE_TABLE_PARAMETER", "RoutingResolverPass"]


@final
class RoutingResolverPass(CompilerPassInterface):
    """Builds the route table from every route loader and routes file the scan found.

    A route loader takes no arguments: what it contributes is fixed by the code
    that ships it, so the table is known before any service exists — which is
    what lets ``setup()`` give the application every route at once. Loaders
    are asked in scan order, the order resources no routes file mentions are
    served in.
    """

    __slots__ = ("_files", "_loaders")

    _loaders: Sequence[tuple[type[RouteLoaderInterface], RouteLoaderMarker]]
    _files: Sequence[RoutesFile]

    def __init__(
        self,
        loaders: Sequence[tuple[type[RouteLoaderInterface], RouteLoaderMarker]],
        files: Sequence[RoutesFile],
    ) -> None:
        """Build from the loader classes and routes files the bundle collected."""
        self._loaders = loaders
        self._files = files

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Ask every loader for its routes, apply the routes files, and store the table.

        Raises:
            InvalidArgumentError: Two loaders claim one resource name, a loader
                cannot be built with no arguments or does not return a
                collection, or a routes file names an unknown resource or route,
                prefixes a fixed resource, or defines a route with no endpoint.
        """
        offered: dict[str, RouteCollection] = {}
        fixed: set[str] = set()
        for loader_class, marker in self._loaders:
            if marker.resource in offered:
                raise InvalidArgumentError(
                    f'Two route loaders provide the resource "{marker.resource}"; '
                    f"{loader_class.__qualname__} is the second."
                )
            offered[marker.resource] = _routes_of(loader_class)
            if not marker.prefixable:
                fixed.add(marker.resource)
        table = RoutesFileLoader(self._files).load(offered, fixed)
        builder.set_parameter(ROUTE_TABLE_PARAMETER, table)
        builder.log(
            self, f"Built a route table of {len(table)} route(s) from {len(offered)} loader(s)."
        )


def _routes_of(loader_class: type[RouteLoaderInterface]) -> RouteCollection:
    name = loader_class.__qualname__
    if inspect.iscoroutinefunction(loader_class.load_routes):
        raise InvalidArgumentError(
            f"The route loader {name} defines load_routes() as a coroutine function; it is a "
            "plain method, called while the kernel compiles."
        )
    try:
        loader = loader_class()
    except TypeError as error:
        raise InvalidArgumentError(
            f"The route loader {name} cannot be built with no arguments ({error}); a route "
            "loader is built while the kernel compiles, before any service exists."
        ) from error
    # A loader is any class carrying the decorator; what it returns is checked here.
    routes = cast("object", loader.load_routes())
    if not isinstance(routes, RouteCollection):
        raise InvalidArgumentError(
            f"The route loader {name} returned {type(routes).__name__} from load_routes(), "
            "not a RouteCollection; load_routes() is a plain method."
        )
    return routes
