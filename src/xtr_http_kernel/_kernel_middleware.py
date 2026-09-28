"""The one middleware the setup call adds: a container scope around each request.

Plain ASGI on purpose — no base class dispatch, no response buffering — so
the scope opens before anything downstream runs and closes only when the
downstream returned, which is after the response's last chunk left. The
scope opener arrives through the constructor rather than an import, so this
module stays free of the container layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast, final

from ._state import FACTORIES_KEY

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractAsyncContextManager

    from starlette.applications import Starlette
    from starlette.types import ASGIApp, Receive, Scope, Send

    MiddlewareFactory = Callable[[ASGIApp], ASGIApp]
    ScopeOpener = Callable[[Starlette], AbstractAsyncContextManager[None]]

__all__ = ["KernelMiddleware"]

_SCOPED_TYPES: Final = frozenset({"http", "websocket"})


@final
class KernelMiddleware:
    """Runs each connection inside the scope its scoped services live in.

    ``http`` and ``websocket`` connections run through the chain the
    application's current life contributed — the factories the setup call
    parked on the application's state, composed over the downstream app —
    with the scope open around the whole of it, so a scoped service lives
    until the response has been sent. The scope closes on every path, a
    failing downstream included; the failure still propagates. The
    ``lifespan`` connection passes through untouched.
    """

    __slots__ = ("_app", "_chain", "_factories", "_open_scope")

    def __init__(self, app: ASGIApp, *, open_scope: ScopeOpener) -> None:
        """Wrap ``app``, opening scopes through ``open_scope``."""
        self._app = app
        self._open_scope = open_scope
        self._factories: tuple[MiddlewareFactory, ...] | None = None
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

        The factories tuple is frozen per application life, so its identity
        tells whether the cached chain still stands.
        """
        factories = cast(
            "tuple[MiddlewareFactory, ...]",
            getattr(application.state, FACTORIES_KEY, ()),
        )
        if factories is not self._factories:
            chain: ASGIApp = self._app
            # The tuple holds the outermost factory first, so it wraps last.
            for factory in reversed(factories):
                chain = factory(chain)
            self._factories = factories
            self._chain = chain
        return self._chain
