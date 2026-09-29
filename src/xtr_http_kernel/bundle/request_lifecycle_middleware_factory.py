"""The middleware factory the bundle tags for the kernel to order into the stack."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

# Read at runtime: the container fills the constructor from this annotation.
from xtr_event_dispatcher_contracts import EventDispatcherInterface  # noqa: TC002 — read at runtime

from xtr_http_kernel.request_lifecycle_middleware import RequestLifecycleMiddleware

if TYPE_CHECKING:
    from starlette.types import ASGIApp

__all__ = ["RequestLifecycleMiddlewareFactory"]


@final
class RequestLifecycleMiddlewareFactory:
    """Wraps a downstream app in the lifecycle middleware, around the container's dispatcher.

    Tagged ``http_kernel.middleware`` with the config's
    ``middleware_priority`` as the tag's ``priority``, so the bundle orders
    it into the stack when the kernel is built — highest outermost.
    """

    __slots__ = ("_dispatcher",)

    def __init__(self, dispatcher: EventDispatcherInterface) -> None:
        """Hand ``dispatcher`` to every middleware built."""
        self._dispatcher = dispatcher

    def __call__(self, app: ASGIApp) -> ASGIApp:
        """Return ``app`` wrapped in the lifecycle middleware."""
        return RequestLifecycleMiddleware(app, dispatcher=self._dispatcher)
