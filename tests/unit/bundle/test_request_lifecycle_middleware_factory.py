"""Unit tests for the middleware factory the bundle contributes."""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, cast

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from xtr_event_dispatcher import EventDispatcher
from xtr_http_message import HttpFactory

from xtr_http_kernel import (
    ExceptionEvent,
    FinishRequestEvent,
    RequestEvent,
    RequestLifecycleMiddleware,
    TerminateEvent,
)
from xtr_http_kernel.bridge import HttpMessageFactory, ResponseFactory
from xtr_http_kernel.bundle.request_lifecycle_middleware_factory import (
    RequestLifecycleMiddlewareFactory,
)

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send


def _messages() -> HttpMessageFactory:
    one = HttpFactory()
    return HttpMessageFactory(one, one, one, ResponseFactory(), one)


async def _app(scope: object, receive: object, send: object) -> None:
    del scope, receive, send


def test_it_carries_no_priority_of_its_own() -> None:
    factory = RequestLifecycleMiddlewareFactory(EventDispatcher(), _messages())

    assert not hasattr(factory, "priority")


def test_it_wraps_the_app_in_the_lifecycle_middleware() -> None:
    factory = RequestLifecycleMiddlewareFactory(EventDispatcher(), _messages())

    wrapped = factory(_app)

    assert isinstance(wrapped, RequestLifecycleMiddleware)


async def _answered(app: object, host: bytes) -> list[Message]:
    sent: list[Message] = []

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(b"host", host)],
        "server": ("127.0.0.1", 8000),
    }
    await cast("ASGIApp", app)(scope, receive, send)
    return sent


async def _hello(scope: Scope, receive: Receive, send: Send) -> None:
    await PlainTextResponse("hello")(scope, receive, send)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("host", "status"),
    [(b"app.test", 200), (b"api.app.test:8000", 200), (b"evil.test", 400), (b"a b", 400)],
)
async def test_a_host_outside_the_trusted_hosts_gets_400_before_the_lifecycle(
    host: bytes, status: int
) -> None:
    dispatcher = EventDispatcher()
    requests: list[RequestEvent] = []
    dispatcher.add_listener(RequestEvent, requests.append)
    factory = RequestLifecycleMiddlewareFactory(
        dispatcher, _messages(), trusted_hosts=("app.test", "*.app.test")
    )

    sent = await _answered(factory(_hello), host)

    assert sent[0]["status"] == status
    assert len(requests) == (1 if status == 200 else 0)


@pytest.mark.anyio
async def test_no_trusted_hosts_lets_any_host_through() -> None:
    factory = RequestLifecycleMiddlewareFactory(EventDispatcher(), _messages())

    sent = await _answered(factory(_hello), b"anything.test")

    assert sent[0]["status"] == 200


def _journal(dispatcher: EventDispatcher) -> list[str]:
    journal: list[str] = []

    def note(event: object) -> None:
        journal.append(type(event).__name__.removesuffix("Event"))

    for event_type in (RequestEvent, ExceptionEvent, FinishRequestEvent, TerminateEvent):
        dispatcher.add_listener(event_type, note)
    return journal


async def _posted(app: ASGIApp, body: bytes, *, declared: int | None = None) -> list[Message]:
    sent: list[Message] = []
    chunks = [{"type": "http.request", "body": body, "more_body": False}]

    async def receive() -> Message:
        return chunks.pop(0) if chunks else {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        sent.append(message)

    headers = [(b"host", b"app.test"), (b"content-type", b"application/json")]
    if declared is not None:
        headers.append((b"content-length", str(declared).encode()))
    scope = {
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": headers,
        "server": ("127.0.0.1", 8000),
    }
    with suppress(Exception):
        await app(scope, receive, send)
    return sent


async def _count(request: Request) -> PlainTextResponse:
    return PlainTextResponse(f"{len(await request.body())} bytes")


async def _ignore(request: Request) -> PlainTextResponse:
    del request
    return PlainTextResponse("hello")


# Applications as a framework builds them: a read past the limit raises the framework's
# own 413, which its error handling answers.
_reads_the_body = Starlette(routes=[Route("/", _count, methods=["POST"])])
_never_reads_it = Starlette(routes=[Route("/", _ignore, methods=["POST"])])


@pytest.mark.anyio
async def test_a_body_within_the_limit_is_read() -> None:
    factory = RequestLifecycleMiddlewareFactory(EventDispatcher(), _messages(), max_body_size=10)

    sent = await _posted(factory(_reads_the_body), b"0123456789")

    assert sent[0]["status"] == 200


@pytest.mark.anyio
@pytest.mark.parametrize(
    "app", [_reads_the_body, _never_reads_it], ids=["reads-the-body", "never-reads-it"]
)
@pytest.mark.parametrize("declared", [None, 11], ids=["chunked", "content-length"])
async def test_a_body_over_the_limit_gets_413_and_is_no_application_failure(
    app: ASGIApp, declared: int | None
) -> None:
    dispatcher = EventDispatcher()
    journal = _journal(dispatcher)
    factory = RequestLifecycleMiddlewareFactory(dispatcher, _messages(), max_body_size=10)

    sent = await _posted(factory(app), b"0123456789A", declared=declared)

    statuses = [message["status"] for message in sent if message["type"] == "http.response.start"]
    if app is _never_reads_it and declared is None:
        assert statuses == [200]  # nothing read it, so nothing was over a limit
        return
    assert statuses[-1] == 413
    assert "Exception" not in journal
    assert journal[-2:] == ["FinishRequest", "Terminate"]


@pytest.mark.anyio
async def test_no_limit_reads_any_body() -> None:
    factory = RequestLifecycleMiddlewareFactory(EventDispatcher(), _messages(), max_body_size=None)

    sent = await _posted(factory(_reads_the_body), b"x" * 20_000_000)

    assert sent[0]["status"] == 200
