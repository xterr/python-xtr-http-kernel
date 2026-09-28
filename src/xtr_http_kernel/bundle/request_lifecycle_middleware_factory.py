"""The middleware factory the bundle tags for the setup call to compose."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

# Read at runtime: the container fills the constructor from this annotation.
from xtr_event_dispatcher_contracts import EventDispatcherInterface  # noqa: TC002

from xtr_http_kernel.request_lifecycle_middleware import RequestLifecycleMiddleware

if TYPE_CHECKING:
    from starlette.types import ASGIApp

__all__ = ["RequestLifecycleMiddlewareFactory"]


@final
class RequestLifecycleMiddlewareFactory:
    """Wraps a downstream app in the lifecycle middleware, around the container's dispatcher.

    Tagged ``http_kernel.middleware``, so the setup call collects it when the
    application's lifespan starts; ``priority`` — the config's
    ``middleware_priority`` — is where it sits in the composed chain, highest
    outermost.

    Attributes:
        priority: The factory's place among the contributed factories.
    """

    __slots__ = ("_dispatcher", "priority")

    def __init__(self, dispatcher: EventDispatcherInterface, priority: int = 0) -> None:
        """Hand ``dispatcher`` to every middleware built, sitting at ``priority``."""
        self._dispatcher = dispatcher
        self.priority = priority

    def __call__(self, app: ASGIApp) -> ASGIApp:
        """Return ``app`` wrapped in the lifecycle middleware."""
        return RequestLifecycleMiddleware(app, dispatcher=self._dispatcher)
