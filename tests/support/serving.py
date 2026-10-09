"""Driving a set-up application the way a server does.

The ASGI transport drives the application directly, so nothing runs the
lifespan or copies its state into each connection's scope the way a server
does. :func:`serving` is that server: it enters the application's lifespan,
bridges the yielded state into every request, and hands out a client.

:func:`driving` is the same server without the client, for the connections a
client cannot make: a socket, or a request whose body must arrive in chunks
of a chosen size while the test watches what the application allocates.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, TypeAlias, cast, final

import httpx

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping

    from fastapi import FastAPI
    from starlette.types import Message, Receive, Scope, Send

__all__ = ["Drive", "ServerStateBridge", "driving", "serving"]

Drive: TypeAlias = "Callable[[Scope, Receive], Awaitable[list[Message]]]"
"""Runs one connection at the application and returns everything it sent."""


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


@asynccontextmanager
async def driving(app: FastAPI) -> AsyncGenerator[Drive, None]:
    """Serve ``app`` for one application life and yield a driver of raw connections.

    What the driver returns is the messages the application sent, so a test
    reads the status, the headers and the body straight off the wire — and a
    failure the application never answered comes back out of the call.
    """
    async with app.router.lifespan_context(app) as state:
        bridge = ServerStateBridge(app, cast("Mapping[str, object] | None", state))

        async def drive(scope: Scope, receive: Receive) -> list[Message]:
            sent: list[Message] = []

            async def send(message: Message) -> None:
                sent.append(message)

            await bridge(scope, receive, send)
            return sent

        yield drive
