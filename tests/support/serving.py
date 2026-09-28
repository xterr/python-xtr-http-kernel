"""Driving a set-up application the way a server does.

The ASGI transport drives the application directly, so nothing runs the
lifespan or copies its state into each connection's scope the way a server
does. :func:`serving` is that server: it enters the application's lifespan,
bridges the yielded state into every request, and hands out a client.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast, final

import httpx

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Mapping

    from fastapi import FastAPI
    from starlette.types import Message, Receive, Scope, Send

__all__ = ["ServerStateBridge", "serving"]


@final
class ServerStateBridge:
    """What a server adds around an application: lifespan state on each request.

    ``on_response_sent`` observes the moment the response's last body chunk
    passed out — the point a server has handed everything to the wire.
    """

    def __init__(
        self,
        app: FastAPI,
        state: Mapping[str, object] | None,
        on_response_sent: Callable[[], None] | None = None,
    ) -> None:
        self._app = app
        self._state = dict(state or {})
        self._on_response_sent = on_response_sent

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope["state"] = dict(self._state)

        async def sending(message: Message) -> None:
            await send(message)
            if (
                self._on_response_sent is not None
                and cast("str", message["type"]) == "http.response.body"
                and not cast("bool", message.get("more_body", False))
            ):
                self._on_response_sent()

        await self._app(scope, receive, send if self._on_response_sent is None else sending)


@asynccontextmanager
async def serving(
    app: FastAPI,
    on_response_sent: Callable[[], None] | None = None,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Serve ``app`` for one application life and yield a client driving it."""
    async with app.router.lifespan_context(app) as state:
        bridge = ServerStateBridge(
            app, cast("Mapping[str, object] | None", state), on_response_sent
        )
        transport = httpx.ASGITransport(app=bridge, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://served.test") as client:
            yield client
