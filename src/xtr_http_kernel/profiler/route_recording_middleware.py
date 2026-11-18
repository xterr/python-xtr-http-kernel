"""Notes which route answered a request, for the profile to show."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from starlette.routing import BaseRoute, Route

from . import _state_keys as keys

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from starlette.types import ASGIApp, Message, Receive, Scope, Send

__all__ = ["RouteRecordingMiddleware"]


@final
class RouteRecordingMiddleware:
    """Writes the matched route onto the request's state bag as its response starts.

    The lifecycle's events carry the request as a message, which knows its
    path parameters but not the route that matched: routing fills that into
    the connection's scope, below the lifecycle. Sitting inside the lifecycle
    middleware, this one sees the response start first, while the scope
    already holds the route, and leaves a plain description of it where a
    data collector reads it.
    """

    __slots__ = ("_app",)

    def __init__(self, app: ASGIApp) -> None:
        """Wrap ``app``."""
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pass the request through, noting the route as the response starts."""
        if cast("str", scope["type"]) != "http":
            await self._app(scope, receive, send)
            return

        async def noting(message: Message) -> None:
            if cast("str", message["type"]) == "http.response.start":
                state = cast("MutableMapping[str, object]", scope.setdefault("state", {}))
                state[keys.ROUTE] = _describe(scope)
            await send(message)

        await self._app(scope, receive, noting)


def _describe(scope: Scope) -> dict[str, object]:
    route = cast("object", scope.get("route"))
    params = cast("dict[str, object]", scope.get("path_params", {}))
    described: dict[str, object] = {
        "matched": isinstance(route, BaseRoute),
        "path_params": {str(name): str(value) for name, value in params.items()},
    }
    if isinstance(route, Route):
        endpoint = cast("object", route.endpoint)
        qualified = getattr(endpoint, "__qualname__", type(endpoint).__qualname__)
        described.update(
            {
                "name": route.name,
                "path": route.path,
                "methods": sorted(route.methods or ()),
                "endpoint": f"{getattr(endpoint, '__module__', '')}.{qualified}",
            }
        )
    elif isinstance(route, BaseRoute):
        described["name"] = getattr(route, "name", type(route).__name__)
    return described
