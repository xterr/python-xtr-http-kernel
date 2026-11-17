"""Serving each connection in a context detached from any earlier request's work.

A server may start a connection's task from a copy of the context of an
earlier request on the same socket — still open, mid-request. Everything the
application runs for the connection, from the outermost middleware in, then
starts in that request's unit of work, reading its services and its
connection. So the application's whole middleware stack runs each ``http`` and
``websocket`` connection in a task started in a detached copy of the context:
what the server and outer wrappers put there is kept, an earlier request's
unit of work and connection are not. The ``lifespan`` connection passes
through untouched: it is no request's.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Final, cast, final

from xtr_dependency_injection.integration import detached_context

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

__all__ = ["DetachedConnections"]

_DETACHED_TYPES: Final = frozenset({"http", "websocket"})


@final
class DetachedConnections:
    """Runs ``http`` and ``websocket`` connections of ``app`` in a detached context each.

    Each runs as a task of its own, awaited here, so what it raises is raised
    here and cancelling the caller — a server stopping the connection —
    cancels it.
    """

    __slots__ = ("_app",)

    def __init__(self, app: ASGIApp) -> None:
        """Detach every request connection ``app`` serves."""
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Serve one connection, detached when it is a request."""
        if cast("str", scope["type"]) not in _DETACHED_TYPES:
            await self._app(scope, receive, send)
            return
        await asyncio.get_running_loop().create_task(
            self._serve(scope, receive, send), context=detached_context()
        )

    async def _serve(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self._app(scope, receive, send)
