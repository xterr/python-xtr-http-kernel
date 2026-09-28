"""The one middleware the setup call adds: a container scope around each request.

Plain ASGI on purpose — no base class dispatch, no response buffering — so
the scope opens before anything downstream runs and closes only when the
downstream returned, which is after the response's last chunk left. The
scope opener arrives through the constructor rather than an import, so this
module stays free of the container layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast, final

from ._state import STACK_KEY

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractAsyncContextManager

    from starlette.applications import Starlette
    from starlette.types import ASGIApp, Receive, Scope, Send

    from .middleware_stack import MiddlewareStack

    ScopeOpener = Callable[[Starlette], AbstractAsyncContextManager[None]]

__all__ = ["KernelMiddleware"]

_SCOPED_TYPES: Final = frozenset({"http", "websocket"})


@final
class KernelMiddleware:
    """Runs each connection inside the scope its scoped services live in.

    ``http`` and ``websocket`` connections run through the middleware stack
    the application's current life parked on its state — composed over the
    downstream app — with the scope open around the whole of it, so a
    scoped service lives until the response has been sent. The scope closes
    on every path, a failing downstream included; the failure still
    propagates. The ``lifespan`` connection passes through untouched.
    """

    __slots__ = ("_app", "_chain", "_open_scope", "_stack")

    def __init__(self, app: ASGIApp, *, open_scope: ScopeOpener) -> None:
        """Wrap ``app``, opening scopes through ``open_scope``."""
        self._app = app
        self._open_scope = open_scope
        self._stack: MiddlewareStack | None = None
        self._chain: ASGIApp = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Carry one connection through, scoped when it is a request."""
        if cast("str", scope["type"]) not in _SCOPED_TYPES:
            await self._app(scope, receive, send)
            return
        application = cast("Starlette", scope["app"])
        chain = self._composed(application)
        async with self._open_scope(application):
            await chain(scope, receive, send)

    def _composed(self, application: Starlette) -> ASGIApp:
        """Return the chain for the application's current life, composed once.

        The stack is frozen per application life, so its identity tells
        whether the cached chain still stands.
        """
        stack = cast(
            "MiddlewareStack | None",
            getattr(application.state, STACK_KEY, None),
        )
        if stack is not self._stack:
            self._stack = stack
            self._chain = self._app if stack is None else stack.wrap(self._app)
        return self._chain
