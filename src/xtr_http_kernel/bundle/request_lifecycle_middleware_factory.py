"""The middleware factory the bundle tags for the kernel to order into the stack."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

# Read at runtime: the container fills the constructor from these annotations.
from xtr_event_dispatcher_contracts import EventDispatcherInterface  # noqa: TC002 — read at runtime

from xtr_http_kernel.bridge.http_message_factory_interface import (  # noqa: TC001 — read at runtime, as above
    HttpMessageFactoryInterface,
)
from xtr_http_kernel.request_lifecycle_middleware import RequestLifecycleMiddleware

if TYPE_CHECKING:
    from starlette.types import ASGIApp

__all__ = ["RequestLifecycleMiddlewareFactory"]


@final
class RequestLifecycleMiddlewareFactory:
    """Wraps a downstream app in the lifecycle middleware, around the container's dispatcher.

    Tagged ``http_kernel.middleware`` with the config's
    ``middleware_priority`` as the tag's ``priority``, so the bundle orders
    it into the stack when the kernel is built — highest outermost. The
    message factory it hands the middleware is the container's own, so the
    served request the lifecycle builds its events on is the one the
    application's factories are behind.
    """

    __slots__ = ("_dispatcher", "_message_factory")

    def __init__(
        self,
        dispatcher: EventDispatcherInterface,
        message_factory: HttpMessageFactoryInterface,
    ) -> None:
        """Hand ``dispatcher`` and ``message_factory`` to every middleware built."""
        self._dispatcher = dispatcher
        self._message_factory = message_factory

    def __call__(self, app: ASGIApp) -> ASGIApp:
        """Return ``app`` wrapped in the lifecycle middleware."""
        return RequestLifecycleMiddleware(
            app, dispatcher=self._dispatcher, message_factory=self._message_factory
        )
