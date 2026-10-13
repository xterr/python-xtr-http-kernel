"""Declaring a class as a source of routes.

A bundle ships its routes as a loader::

    @as_route_loader("oauth2_server")
    class OAuth2ServerRouteLoader:
        def load_routes(self) -> RouteCollection: ...

Once the module is scanned — by the application's kernel, or by a bundle with
``services.load(...)`` — the class is built with no arguments while the kernel
compiles, and its routes join the application's table under ``resource``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, TypeVar

from xtr_http_kernel.routing.exception.invalid_argument_error import InvalidArgumentError

from .route_loader_marker import RouteLoaderMarker

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["ROUTE_LOADER_ATTRIBUTE", "as_route_loader", "route_loaders_of"]

#: Where the marker is kept on the class.
ROUTE_LOADER_ATTRIBUTE: Final = "__xtr_route_loader__"

T = TypeVar("T", bound=type)


def as_route_loader(resource: str, /, *, prefixable: bool = True) -> Callable[[T], T]:
    """Declare a class providing ``load_routes()`` as the source of a named set of routes.

    Args:
        resource: The name an application's routes file imports the routes by.
        prefixable: Whether an application may move the routes under a path
            prefix; pass ``False`` for routes a standard puts at a fixed place.

    Raises:
        InvalidArgumentError: The resource name is empty, or the class has no
            ``load_routes`` method.
    """
    if not resource.strip():
        raise InvalidArgumentError("A route loader needs a resource name.")
    marker = RouteLoaderMarker(resource, prefixable)

    def declare(target: T) -> T:
        if not callable(getattr(target, "load_routes", None)):
            raise InvalidArgumentError(
                f"The route loader {target.__qualname__} has no load_routes() method."
            )
        setattr(target, ROUTE_LOADER_ATTRIBUTE, marker)
        return target

    return declare


def route_loaders_of(obj: object) -> tuple[RouteLoaderMarker, ...]:
    """Return the marker ``obj`` itself was declared with — never one a parent carries."""
    if not isinstance(obj, type):
        return ()
    marker = vars(obj).get(ROUTE_LOADER_ATTRIBUTE)
    return (marker,) if isinstance(marker, RouteLoaderMarker) else ()
