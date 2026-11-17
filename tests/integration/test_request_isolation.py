"""A request reads and logs as itself, whatever context its task was started from.

A server gives no promise about the context a request's task starts with: on
a kept-alive connection it may be a copy of an earlier request's, taken once
that request had published its connection, opened its unit of work and bound
its log context. The same thing happens, with no server at all, when a route
starts a task that sends a request to the application it belongs to — the
task, and the request in it, begin with a copy of the first request's
context, mid-flight. That is how these tests start one request from another's.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, Annotated, cast, final

import anyio
import httpx
import pytest
from fastapi import FastAPI, File, Form, Request, UploadFile, WebSocket
from xtr_dependency_injection import Injected, Kernel, current_unit_of_work
from xtr_dependency_injection.exception import FastapiIntegrationError
from xtr_dependency_injection.integration.fastapi import current_connection
from xtr_logging import bind_context, current_context, in_unit
from xtr_logging.bundle import LoggingBundle

from tests.fixtures.isolation_app.listeners import CUSTOMERS, READ, Reading
from tests.support.bundles import Tick, TickBundle
from tests.support.serving import serving
from xtr_http_kernel import setup
from xtr_http_kernel.bundle import HttpKernelBundle

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

pytestmark = pytest.mark.anyio

OUTSIDE: list[tuple[str, bool, bool, bool, object]] = []
"""Per request, as middleware outside the kernel's saw it.

Its path; whether a unit of work was open, a connection published, a log unit
open; and the ``customer`` the log context held.
"""

SOCKETS: list[tuple[str, bool, object]] = []
"""Per websocket, as its handler saw it: its tick's token, its own connection, the customer."""

_OUTER: ContextVar[str] = ContextVar("test_request_isolation_outer", default="unset")


@pytest.fixture(autouse=True)
def _forget_the_readings() -> None:
    READ.clear()
    CUSTOMERS.clear()
    OUTSIDE.clear()
    SOCKETS.clear()


def _published() -> bool:
    try:
        _ = current_connection()
    except FastapiIntegrationError:
        return False
    return True


@final
class _Watching:
    """Middleware added after the setup call: outside the kernel's, around everything else."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if cast("str", scope["type"]) == "http":
            OUTSIDE.append(
                (
                    cast("str", scope["path"]),
                    current_unit_of_work() is not None,
                    _published(),
                    in_unit(),
                    current_context().get("customer"),
                )
            )
        await self._app(scope, receive, send)


async def _open_a_socket(application: ASGIApp) -> None:
    """Open, then close, a websocket at ``/ws`` of ``application``, from this context."""
    incoming: list[Message] = [{"type": "websocket.connect"}, {"type": "websocket.disconnect"}]

    async def receive() -> Message:
        return incoming.pop(0)

    async def send(message: Message) -> None:
        del message

    scope: Scope = {
        "type": "websocket",
        "path": "/ws",
        "raw_path": b"/ws",
        "query_string": b"",
        "headers": [],
        "scheme": "ws",
        "server": ("served.test", 80),
        "client": ("client.test", 1234),
        "subprotocols": [],
        "asgi": {"version": "3.0"},
    }
    await application(scope, receive, send)


def _application(clients: list[httpx.AsyncClient]) -> FastAPI:
    """Return the application; ``clients`` holds the client its relay route sends through."""
    app = FastAPI()

    @app.post("/documents")
    async def documents(
        title: Annotated[str, Form()],
        doc: Annotated[UploadFile, File()],
        tick: Injected[Tick],
    ) -> dict[str, object]:
        del tick
        return {"title": title, "size": doc.size}

    @app.get("/plain")
    async def plain() -> dict[str, str]:
        return {"plain": "yes"}

    @app.post("/relay/{target}")
    async def relay(
        target: str,
        title: Annotated[str, Form()],
        tick: Injected[Tick],
        request: Request,
    ) -> dict[str, object]:
        # This request's marker has resolved, so its connection is published
        # and its form is parsed, and its unit of work is open with a key
        # bound in it: the task started below begins with all of that.
        del title
        bind_context({"customer": "outer"})
        answered: list[httpx.Response] = []

        async def send() -> None:
            if target == "documents":
                answered.append(
                    await clients[0].post(
                        "/documents",
                        data={"title": "inner"},
                        files={"doc": ("inner.txt", b"inner body", "text/plain")},
                    )
                )
            else:
                answered.append(await clients[0].get("/plain"))

        if target == "ws":
            await _open_a_socket(cast("ASGIApp", request.app))
            return {"tick": tick.token}
        async with anyio.create_task_group() as tasks:
            _ = tasks.start_soon(send)
        started = answered[0]
        return {
            "status": started.status_code,
            "answer": started.json(),
            "customer": current_context().get("customer"),
        }

    @app.websocket("/ws")
    async def socket(websocket: WebSocket, tick: Injected[Tick]) -> None:
        await websocket.accept()
        SOCKETS.append(
            (tick.token, current_connection() is websocket, current_context().get("customer"))
        )
        await websocket.close()

    setup(
        app,
        Kernel(
            "tests.fixtures.isolation_app",
            env="test",
            bundles={
                HttpKernelBundle: {"all": True},
                LoggingBundle: {"all": True},
                TickBundle: {"all": True},
            },
        ),
    )
    app.add_middleware(_Watching)
    return app


async def test_a_request_started_from_anothers_context_reads_its_own_body() -> None:
    clients: list[httpx.AsyncClient] = []

    async with serving(_application(clients)) as client:
        clients.append(client)
        response = await client.post("/relay/documents", data={"title": "outer"})

    # The route behind the listener was handed the inner request's own bytes,
    # and the listener read the inner request's own form.
    assert response.json()["answer"] == {"title": "inner", "size": 10}
    assert list(READ) == [
        Reading("/relay/documents", None, "outer"),
        Reading("/documents", None, "inner"),
    ]


async def test_a_request_started_from_anothers_context_has_no_connection_until_its_own() -> None:
    clients: list[httpx.AsyncClient] = []

    async with serving(_application(clients)) as client:
        clients.append(client)
        response = await client.post("/relay/plain", data={"title": "outer"})

    assert response.json()["answer"] == {"plain": "yes"}
    # The inner route declared no marker, so nothing was ever published for
    # it: the outer request's connection is not its own.
    assert list(READ) == [Reading("/relay/plain", None, "outer"), Reading("/plain", None, None)]


async def test_a_request_started_from_anothers_context_does_not_log_under_its_keys() -> None:
    clients: list[httpx.AsyncClient] = []

    async with serving(_application(clients)) as client:
        clients.append(client)
        response = await client.post("/relay/plain", data={"title": "outer"})

    # The inner request arrived with the outer one's key in its context, and
    # found nothing bound once its own unit of work had begun.
    assert list(CUSTOMERS) == [None, None]
    # The outer request, back in its own unit, still logs under its key.
    assert response.json()["customer"] == "outer"


async def test_middleware_outside_the_kernel_sees_no_unit_of_an_earlier_request() -> None:
    clients: list[httpx.AsyncClient] = []

    async with serving(_application(clients)) as client:
        clients.append(client)
        _ = await client.post("/relay/plain", data={"title": "outer"})

    # The inner request was started inside the outer one's open unit, with its
    # connection published: outside the kernel's middleware it sees neither.
    assert [(path, unit, connection) for path, unit, connection, _, _ in OUTSIDE] == [
        ("/relay/plain", False, False),
        ("/plain", False, False),
    ]


async def test_outer_middleware_of_a_pipelined_request_logs_nothing_into_the_earlier_unit() -> None:
    clients: list[httpx.AsyncClient] = []

    async with serving(_application(clients)) as client:
        clients.append(client)
        _ = await client.post("/relay/plain", data={"title": "outer"})

    # The outer request's log unit was open, with a key bound in it, when the
    # inner one began: outside the kernel's middleware it finds neither.
    assert [(path, log_unit, customer) for path, _, _, log_unit, customer in OUTSIDE] == [
        ("/relay/plain", False, None),
        ("/plain", False, None),
    ]


async def test_a_websocket_starts_detached_from_an_earlier_request() -> None:
    clients: list[httpx.AsyncClient] = []

    async with serving(_application(clients)) as client:
        clients.append(client)
        response = await client.post("/relay/ws", data={"title": "outer"})

    [(token, own_connection, _)] = SOCKETS
    assert own_connection
    assert token != response.json()["tick"]


async def test_a_websocket_reads_no_log_value_of_an_earlier_request() -> None:
    clients: list[httpx.AsyncClient] = []

    async with serving(_application(clients)) as client:
        clients.append(client)
        _ = await client.post("/relay/ws", data={"title": "outer"})

    [(_, _, customer)] = SOCKETS
    assert customer is None


async def test_context_set_by_an_outer_wrapper_reaches_the_request() -> None:
    clients: list[httpx.AsyncClient] = []
    app = _application(clients)
    seen: list[str] = []

    @app.get("/outer")
    async def outer() -> dict[str, str]:
        seen.append(_OUTER.get())
        return {}

    async def wrapper(scope: Scope, receive: Receive, send: Send) -> None:
        if cast("str", scope["type"]) == "http":
            _ = _OUTER.set("set by the wrapper")
        await app(scope, receive, send)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=wrapper)
        async with httpx.AsyncClient(transport=transport, base_url="http://served.test") as plain:
            _ = await plain.get("/outer")

    assert seen == ["set by the wrapper"]
