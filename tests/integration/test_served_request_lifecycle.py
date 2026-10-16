"""The served request behind the lifecycle: the acceptance suite of the message switch.

The lifecycle's events carry the request as a message — one served request
per connection, its body read only when a listener asks to read it. These
are the guarantees that switch has to hold: nothing is buffered unless a
listener reads, a listener that does read leaves the endpoint its exact
bytes, one instance reaches every event and the route, a form still parses
behind a reading listener, a socket passes through, and the moments a
listener may answer still answer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Final, cast

import pytest
from fastapi import FastAPI, File, Form, Request, UploadFile, WebSocket
from starlette.datastructures import FormData
from starlette.responses import PlainTextResponse
from xtr_dependency_injection import Injected, Kernel

# Read at runtime: the framework evaluates a route's annotations.
from xtr_http_message_contracts import ServerRequestInterface

import tests.fixtures.lifecycle_app.listeners as listening
from tests.support.asgi_requests import asgi_scope
from tests.support.serving import driving, serving
from xtr_http_kernel import setup
from xtr_http_kernel.bridge import Response
from xtr_http_kernel.bundle import HttpKernelBundle

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.types import Message, Receive, Scope

pytestmark = pytest.mark.anyio

_CHUNK: Final = 64 * 1024
"""How much of the streamed body arrives at a time."""

_CHUNKS: Final = 8
"""Enough chunks that a buffer would have to hold them all."""

HELD: Final[list[UploadFile]] = []
"""The uploaded file the form route held, for a test to inspect afterwards."""

SEEN_IN_ROUTES: Final[list[int]] = []
"""The identity of every message a route was handed, in order."""


@pytest.fixture(autouse=True)
async def _quiet_listeners() -> AsyncIterator[None]:
    listening.READ_BODY = False
    listening.ANSWER = None
    listening.SEEN.clear()
    listening.BODIES.clear()
    listening.LIFECYCLE.clear()
    HELD.clear()
    SEEN_IN_ROUTES.clear()
    yield
    listening.READ_BODY = False
    listening.ANSWER = None


def _kernel() -> Kernel:
    return Kernel(
        "tests.fixtures.lifecycle_app",
        env="test",
        bundles={HttpKernelBundle: {"all": True}},
    )


def _chunked() -> Receive:
    remaining = _CHUNKS

    async def receive() -> Message:
        nonlocal remaining
        if remaining == 0:
            return {"type": "http.request", "body": b"", "more_body": False}
        remaining -= 1
        return {"type": "http.request", "body": b"x" * _CHUNK, "more_body": True}

    return receive


SEEN_CHUNKS: Final[list[int]] = []
"""The size of every chunk the streaming route's own stream saw."""


def _streaming_application() -> FastAPI:
    app = FastAPI()

    @app.post("/streamed")
    async def streamed(request: Request) -> dict[str, object]:
        SEEN_CHUNKS.clear()
        async for chunk in request.stream():
            if chunk:
                SEEN_CHUNKS.append(len(chunk))
        return {"chunks": SEEN_CHUNKS}

    setup(app, _kernel())
    return app


async def test_a_streaming_route_behind_a_listener_that_reads_no_body_is_not_buffered() -> None:
    async with driving(_streaming_application()) as drive:
        _ = await drive(
            asgi_scope(
                "POST",
                path="/streamed",
                headers=((b"host", b"served.test"), (b"content-type", b"text/plain")),
            ),
            _chunked(),
        )

    # The endpoint's stream saw every chunk as it arrived — none swallowed by
    # a copy of the body — and the listener read nothing.
    assert SEEN_CHUNKS == [_CHUNK] * _CHUNKS
    assert listening.BODIES == []
    assert listening.READ_BODY is False


async def test_a_listener_that_reads_the_body_leaves_the_endpoint_its_exact_bytes() -> None:
    def echoing() -> FastAPI:
        app = FastAPI()

        @app.post("/echo")
        async def echo(request: Request) -> dict[str, str]:
            return {"body": (await request.body()).decode()}

        setup(app, _kernel())
        return app

    payload = "exact bytes, every one of them"

    listening.READ_BODY = True
    async with serving(echoing()) as client:
        read = await client.post("/echo", content=payload.encode())

    assert [payload.encode()] == listening.BODIES
    assert read.json() == {"body": payload}

    listening.READ_BODY = False
    async with serving(echoing()) as client:
        untouched = await client.post("/echo", content=payload.encode())

    # The replay receive: byte-identical to the run nobody read.
    assert (read.status_code, read.content) == (untouched.status_code, untouched.content)


async def test_one_served_request_across_the_events_and_the_route() -> None:
    def identity_application() -> FastAPI:
        app = FastAPI()

        @app.get("/identity")
        async def identity(message: Injected[ServerRequestInterface]) -> dict[str, bool]:
            SEEN_IN_ROUTES.append(id(message))
            return {"same": True}

        @app.get("/failing")
        async def failing(message: Injected[ServerRequestInterface]) -> dict[str, bool]:
            SEEN_IN_ROUTES.append(id(message))
            raise RuntimeError("after the message was held")

        setup(app, _kernel())
        return app

    async with serving(identity_application()) as client:
        _ = await client.get("/identity")
        _ = await client.get("/failing")

    # Two requests, each one served request: every event of a request carried
    # the instance its route was handed — the D11 enabler.
    (first, second) = SEEN_IN_ROUTES
    assert [name for name, _ in listening.LIFECYCLE] == [
        "request",
        "response",
        "finish",
        "terminate",
        "request",
        "exception",
        "finish",
        "terminate",
    ]
    assert {identity for _, identity in listening.LIFECYCLE[:4]} == {first}
    assert {identity for _, identity in listening.LIFECYCLE[4:]} == {second}


async def test_a_form_post_behind_a_body_reading_listener_still_parses() -> None:
    def submitting() -> FastAPI:
        app = FastAPI()

        @app.post("/submit")
        async def submit(
            title: Annotated[str, Form()],
            doc: Annotated[UploadFile, File()],
        ) -> dict[str, object]:
            HELD.append(doc)
            return {"title": title, "read": (await doc.read()).decode()}

        setup(app, _kernel())
        return app

    listening.READ_BODY = True
    async with serving(submitting()) as client:
        accepted = await client.post(
            "/submit", data={"title": "dune"}, files={"doc": ("a.txt", b"body", "text/plain")}
        )
        refused = await client.post("/submit", files={"doc": ("a.txt", b"body", "text/plain")})

    assert accepted.json() == {"title": "dune", "read": "body"}
    # The form the listener's read parsed is closed as the request leaves —
    # the file the route held is shut, not leaked.
    assert HELD[0].file.closed
    # A refusal is the framework's own, byte for byte, behind a reading
    # listener: the replay gave it its body back.
    assert refused.status_code == 422
    listening.READ_BODY = False
    async with serving(submitting()) as client:
        untouched = await client.post("/submit", files={"doc": ("a.txt", b"body", "text/plain")})
    assert (refused.status_code, refused.content) == (untouched.status_code, untouched.content)


def _describe(parsed: object) -> object:
    """Return a parsed body as plain data a test can compare."""
    if isinstance(parsed, FormData):
        fields: dict[str, str] = {
            name: value for name, value in parsed.items() if isinstance(value, str)
        }
        return fields
    if isinstance(parsed, dict):
        return cast("dict[str, object]", parsed)
    return None


async def test_a_parsed_body_answers_before_the_endpoint_reads_anything() -> None:
    def corner_application() -> FastAPI:
        app = FastAPI()

        @app.post("/corner")
        async def corner(message: Injected[ServerRequestInterface]) -> dict[str, object]:
            before = message.get_parsed_body()
            body = await message.get_body().get_contents()
            return {
                "before": before is None,
                "after": _describe(message.get_parsed_body()),
                "body": body.decode(),
            }

        setup(app, _kernel())
        return app

    async with serving(corner_application()) as client:
        form = await client.post("/corner", data={"title": "dune", "pages": "412"})
        json_object = await client.post("/corner", json={"title": "dune"})
        json_list = await client.post(
            "/corner", content=b"[1, 2]", headers={"content-type": "application/json"}
        )

    # A body with a parsed side — a form, a JSON object — is materialised
    # before the container hands the message on, so the contract's
    # unconditional wording holds by the time the endpoint asks. A JSON body
    # that is not an object — a list — is materialised like any JSON and
    # still answers no fields: it says none — none of it the framework's
    # business, all of it off the message.
    assert form.json()["before"] is False
    assert form.json()["after"] == {"title": "dune", "pages": "412"}
    assert json_object.json()["before"] is False
    assert json_object.json()["after"] == {"title": "dune"}
    assert json_list.json()["before"] is True
    assert json_list.json()["after"] is None


async def test_a_socket_passes_through_with_no_event_and_no_message() -> None:
    def socket_application() -> FastAPI:
        app = FastAPI()

        @app.websocket("/socket")
        async def socket(websocket: WebSocket) -> None:
            await websocket.accept()
            await websocket.close()

        setup(app, _kernel())
        return app

    incoming = iter(({"type": "websocket.connect"}, {"type": "websocket.disconnect", "code": 1000}))

    async def receive() -> Message:
        return next(incoming, {"type": "websocket.disconnect", "code": 1000})

    scope: dict[str, object] = {
        "type": "websocket",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "path": "/socket",
        "raw_path": b"/socket",
        "root_path": "",
        "query_string": b"",
        "headers": [(b"host", b"served.test")],
        "client": ("127.0.0.1", 51234),
        "server": ("served.test", 80),
        "subprotocols": [],
    }

    async with driving(socket_application()) as drive:
        _sent = await drive(cast("Scope", scope), receive)

    # No event, no message: a socket is not a request, and the lifecycle
    # leaves it alone.
    assert listening.LIFECYCLE == []
    assert listening.SEEN == []


async def test_a_listener_runs_before_a_404_leaves() -> None:
    app = FastAPI()
    setup(app, _kernel())

    async with serving(app) as client:
        response = await client.get("/missing")

    # The request event fires before routing, so an unmatched path is
    # announced — and then answered 404, as the framework would.
    assert response.status_code == 404
    assert listening.SEEN == ["/missing"]


async def test_a_listener_answer_of_either_response_kind_skips_the_application() -> None:
    def plain() -> FastAPI:
        app = FastAPI()

        @app.get("/answerable")
        async def answerable() -> dict[str, bool]:
            SEEN_IN_ROUTES.append(0)
            return {"ran": True}

        setup(app, _kernel())
        return app

    # The framework's own response kind.
    listening.ANSWER = PlainTextResponse("framework", status_code=503)
    async with serving(plain()) as client:
        framework = await client.get("/answerable")

    assert (framework.status_code, framework.text) == (503, "framework")
    assert SEEN_IN_ROUTES == []

    # The bridge's own — a message and a framework response at once.
    answered = Response(503)
    _ = await answered.get_body().write(b"bridge")
    listening.ANSWER = answered.with_header("content-type", "text/plain")
    async with serving(plain()) as client:
        bridge = await client.get("/answerable")

    assert (bridge.status_code, bridge.content) == (503, b"bridge")
    assert SEEN_IN_ROUTES == []
