"""What the router commands report about one route of an application."""

from __future__ import annotations

from dataclasses import dataclass
from types import FunctionType, MethodType
from typing import TYPE_CHECKING, Final, final

from starlette.routing import Mount, WebSocketRoute

if TYPE_CHECKING:
    from starlette.routing import BaseRoute

    from ._route_contexts import RouteView

__all__ = ["RouteDescription"]

_ANY_METHOD: Final = "-"
"""Stands in for a route that answers whatever arrives, or has no method at all."""

_MOUNT: Final = "MOUNT"
_WEBSOCKET: Final = "WEBSOCKET"


@final
@dataclass(frozen=True, slots=True)
class RouteDescription:
    """One line of what a router holds, ready to be printed.

    Built from the routing layer's own view of a route, so the path is the
    one requests are matched against — an included router's prefix already
    applied — rather than the one written at the endpoint.

    Attributes:
        methods: The methods the route answers, comma-separated;
            ``WEBSOCKET`` for a connection route, ``MOUNT`` for a mounted
            application, ``-`` for a route taking whatever arrives.
        path: The path as routing reads it.
        name: The name the route answers to, empty when it has none.
        endpoint: What the route hands the request to, as ``module:qualname``.
    """

    methods: str
    path: str
    name: str
    endpoint: str

    @classmethod
    def of(cls, view: RouteView) -> RouteDescription:
        """Describe the route ``view`` stands for."""
        endpoint = view.endpoint
        return cls(
            methods=_methods(view),
            path=view.path or "",
            name=view.name or "",
            endpoint=_qualified(endpoint if endpoint is not None else _carried(view.route)),
        )


def _methods(view: RouteView) -> str:
    """Name the methods the route answers, or else the kind of route it is."""
    if view.methods:
        return ", ".join(sorted(view.methods))
    if isinstance(view.route, WebSocketRoute):
        return _WEBSOCKET
    if isinstance(view.route, Mount):
        return _MOUNT
    return _ANY_METHOD


def _carried(route: BaseRoute) -> object:
    """Return what a route with no endpoint of its own hands the request to."""
    return route.app if isinstance(route, Mount) else route


def _qualified(target: object) -> str:
    """Name ``target`` as ``module:qualname`` — its type's when it has none of its own."""
    if isinstance(target, (type, FunctionType, MethodType)):
        return f"{target.__module__}:{target.__qualname__}"
    kind = type(target)
    return f"{kind.__module__}:{kind.__qualname__}"
