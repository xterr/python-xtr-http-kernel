"""Declaring a function as the source of one named route resource.

A package ships its routes as a registration function::

    @as_route_resource("webhook")
    def webhook_routes(router: APIRouter) -> None:
        @router.post("/webhook/{type}", name="webhook")
        async def webhook(...) -> Response: ...

Nothing is served until the application's routes files include the resource —
routing is never imported automatically. Once the module is scanned — by the
application's kernel, or by a bundle with ``services.load(...)`` — ``setup``
calls the function with a fresh router of its own, and the application
includes what it wants, where it wants it.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Final, TypeVar, cast

from xtr_http_kernel.routing.exception.invalid_argument_error import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["ROUTE_RESOURCE_ATTRIBUTE", "as_route_resource", "route_resources_of"]

#: Where the resource name is kept on the function.
ROUTE_RESOURCE_ATTRIBUTE: Final = "__xtr_route_resource__"

T = TypeVar("T")


def as_route_resource(resource: str, /) -> Callable[[T], T]:
    """Declare that the decorated function fills the resource ``resource``.

    Args:
        resource: The name an application's routes file includes the routes by.

    Raises:
        InvalidArgumentError: The resource name is blank, or the target is not
            a plain function.
    """
    if not resource.strip():
        raise InvalidArgumentError("A route resource needs a name.")

    def declare(target: T) -> T:
        if not inspect.isfunction(target) or inspect.iscoroutinefunction(target):
            raise InvalidArgumentError(
                "@as_route_resource decorates a plain function filling an APIRouter; "
                f"{getattr(target, '__qualname__', target)!s} is not one."
            )
        setattr(target, ROUTE_RESOURCE_ATTRIBUTE, resource)
        return target

    return declare


def route_resources_of(obj: object) -> tuple[str, ...]:
    """Return the resource ``obj`` itself was declared with — never one a parent carries."""
    if not inspect.isfunction(obj):
        return ()
    declared = cast("object", getattr(obj, "__dict__", {}).get(ROUTE_RESOURCE_ATTRIBUTE))
    return (declared,) if isinstance(declared, str) else ()
