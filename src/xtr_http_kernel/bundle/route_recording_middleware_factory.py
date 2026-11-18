"""The middleware factory the bundle tags when the profiler is on, just inside the lifecycle."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_http_kernel.profiler.route_recording_middleware import RouteRecordingMiddleware

if TYPE_CHECKING:
    from starlette.types import ASGIApp

__all__ = ["RouteRecordingMiddlewareFactory"]


@final
class RouteRecordingMiddlewareFactory:
    """Wraps a downstream app in a :class:`RouteRecordingMiddleware`.

    Tagged one below the lifecycle middleware's priority, so it sits inside
    the lifecycle and notes the route before the response event is dispatched.
    """

    __slots__ = ()

    def __call__(self, app: ASGIApp) -> ASGIApp:
        """Return ``app`` wrapped so its route is noted."""
        return RouteRecordingMiddleware(app)
