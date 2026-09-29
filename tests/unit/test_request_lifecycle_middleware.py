"""Unit tests for :class:`xtr_http_kernel.request_lifecycle_middleware.RequestLifecycleMiddleware`.

The middleware is driven here as what it is — a callable taking a scope, a
receive and a send — so every message it forwards and every event it
dispatches lands in one shared journal, and the order of the two can be read
off a single list.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, TypeVar, cast, final

import pytest
from starlette.responses import PlainTextResponse
from xtr_event_dispatcher import EventDispatcher

from xtr_http_kernel import (
    ExceptionEvent,
    FinishRequestEvent,
    RequestEvent,
    RequestLifecycleMiddleware,
    ResponseEvent,
    TerminateEvent,
)

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

pytestmark = pytest.mark.anyio

_EventT = TypeVar("_EventT")


def _http_scope(path: str = "/books") -> dict[str, object]:
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [(b"host", b"bookshop.test")],
        "client": ("127.0.0.1", 51234),
        "server": ("bookshop.test", 80),
    }


async def _receive() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}


def _journalling_send(journal: list[str]) -> Send:
    async def send(message: Message) -> None:
        kind = cast("str", message["type"])
        if kind == "http.response.start":
            journal.append(f"sent:start:{cast('int', message['status'])}")
        elif kind == "http.response.body":
            body = cast("bytes", message.get("body", b""))
            journal.append(f"sent:body:{body.decode()}")
        else:
            journal.append(f"sent:{kind}")

    return send


def _journalling_dispatcher(journal: list[str]) -> EventDispatcher:
    dispatcher = EventDispatcher()

    async def on_request(_event: RequestEvent) -> None:
        journal.append("request")

    async def on_response(event: ResponseEvent) -> None:
        journal.append(f"response:{event.status_code}")

    async def on_exception(event: ExceptionEvent) -> None:
        journal.append(f"exception:{type(event.exception).__name__}")

    async def on_finish(_event: FinishRequestEvent) -> None:
        journal.append("finish_request")

    async def on_terminate(event: TerminateEvent) -> None:
        journal.append(f"terminate:{event.status_code}")

    dispatcher.add_listener(RequestEvent, on_request)
    dispatcher.add_listener(ResponseEvent, on_response)
    dispatcher.add_listener(ExceptionEvent, on_exception)
    dispatcher.add_listener(FinishRequestEvent, on_finish)
    dispatcher.add_listener(TerminateEvent, on_terminate)
    return dispatcher


def _answering_app(*chunks: bytes) -> ASGIApp:
    async def app(_scope: Scope, _receive: Receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        for chunk in chunks[:-1]:
            await send({"type": "http.response.body", "body": chunk, "more_body": True})
        await send({"type": "http.response.body", "body": chunks[-1], "more_body": False})

    return app


async def test_a_success_dispatches_request_response_finish_and_terminate_in_order() -> None:
    journal: list[str] = []
    middleware = RequestLifecycleMiddleware(
        _answering_app(b"hello"), dispatcher=_journalling_dispatcher(journal)
    )

    await middleware(_http_scope(), _receive, _journalling_send(journal))

    assert journal == [
        "request",
        "response:200",
        "sent:start:200",
        "finish_request",
        "sent:body:hello",
        "terminate:200",
    ]


async def test_finish_request_leaves_before_the_last_chunk_of_a_streamed_body() -> None:
    journal: list[str] = []
    middleware = RequestLifecycleMiddleware(
        _answering_app(b"one", b"two", b"three"),
        dispatcher=_journalling_dispatcher(journal),
    )

    await middleware(_http_scope(), _receive, _journalling_send(journal))

    assert journal == [
        "request",
        "response:200",
        "sent:start:200",
        "sent:body:one",
        "sent:body:two",
        "finish_request",
        "sent:body:three",
        "terminate:200",
    ]


async def test_a_request_listener_answer_skips_the_application() -> None:
    journal: list[str] = []
    dispatcher = _journalling_dispatcher(journal)

    async def answer(event: RequestEvent) -> None:
        event.set_response(PlainTextResponse("down for maintenance", status_code=503))

    dispatcher.add_listener(RequestEvent, answer, priority=100)

    async def app(_scope: Scope, _receive: Receive, _send: Send) -> None:
        journal.append("application ran")

    middleware = RequestLifecycleMiddleware(app, dispatcher=dispatcher)

    await middleware(_http_scope(), _receive, _journalling_send(journal))

    assert "application ran" not in journal
    # ``answer`` stops the event, so the journalling request listener never runs.
    assert journal == [
        "response:503",
        "sent:start:503",
        "finish_request",
        "sent:body:down for maintenance",
        "terminate:503",
    ]


async def test_a_response_listener_adjusts_the_status_and_headers_that_leave() -> None:
    journal: list[str] = []
    dispatcher = _journalling_dispatcher(journal)

    async def adjust(event: ResponseEvent) -> None:
        event.status_code = 201
        event.headers["x-request-id"] = "42"

    dispatcher.add_listener(ResponseEvent, adjust, priority=100)
    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    middleware = RequestLifecycleMiddleware(_answering_app(b"made"), dispatcher=dispatcher)

    await middleware(_http_scope(), _receive, send)

    assert cast("int", sent[0]["status"]) == 201
    assert (b"x-request-id", b"42") in cast("list[tuple[bytes, bytes]]", sent[0]["headers"])
    assert "terminate:201" in journal


async def test_an_unanswered_exception_is_announced_finished_and_re_raised() -> None:
    journal: list[str] = []

    async def app(_scope: Scope, _receive: Receive, _send: Send) -> None:
        raise RuntimeError("boom")

    middleware = RequestLifecycleMiddleware(app, dispatcher=_journalling_dispatcher(journal))

    with pytest.raises(RuntimeError, match="boom"):
        await middleware(_http_scope(), _receive, _journalling_send(journal))

    assert journal == [
        "request",
        "exception:RuntimeError",
        "finish_request",
        "terminate:500",
    ]


async def test_an_exception_listener_answer_leaves_instead_of_the_failure() -> None:
    journal: list[str] = []
    dispatcher = _journalling_dispatcher(journal)

    async def answer(event: ExceptionEvent) -> None:
        event.set_response(PlainTextResponse("mended", status_code=503))

    dispatcher.add_listener(ExceptionEvent, answer, priority=-100)

    async def app(_scope: Scope, _receive: Receive, _send: Send) -> None:
        raise RuntimeError("boom")

    middleware = RequestLifecycleMiddleware(app, dispatcher=dispatcher)

    await middleware(_http_scope(), _receive, _journalling_send(journal))

    assert journal == [
        "request",
        "exception:RuntimeError",
        "response:503",
        "sent:start:503",
        "finish_request",
        "sent:body:mended",
        "terminate:503",
    ]


async def test_a_listener_answer_does_not_swallow_a_cancellation() -> None:
    journal: list[str] = []
    dispatcher = _journalling_dispatcher(journal)

    async def answer(event: ExceptionEvent) -> None:
        event.set_response(PlainTextResponse("mended", status_code=503))

    dispatcher.add_listener(ExceptionEvent, answer, priority=-100)

    async def app(_scope: Scope, _receive: Receive, _send: Send) -> None:
        raise asyncio.CancelledError

    middleware = RequestLifecycleMiddleware(app, dispatcher=dispatcher)

    with pytest.raises(asyncio.CancelledError):
        await middleware(_http_scope(), _receive, _journalling_send(journal))

    assert journal == [
        "request",
        "exception:CancelledError",
        "finish_request",
        "terminate:500",
    ]


async def test_an_exception_after_the_response_started_ignores_a_listener_answer() -> None:
    journal: list[str] = []
    dispatcher = _journalling_dispatcher(journal)

    async def answer(event: ExceptionEvent) -> None:
        event.set_response(PlainTextResponse("too late", status_code=503))

    dispatcher.add_listener(ExceptionEvent, answer, priority=-100)

    async def app(_scope: Scope, _receive: Receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send({"type": "http.response.body", "body": b"partial", "more_body": True})
        raise RuntimeError("mid-stream")

    middleware = RequestLifecycleMiddleware(app, dispatcher=dispatcher)

    with pytest.raises(RuntimeError, match="mid-stream"):
        await middleware(_http_scope(), _receive, _journalling_send(journal))

    assert journal == [
        "request",
        "response:200",
        "sent:start:200",
        "sent:body:partial",
        "exception:RuntimeError",
        "finish_request",
        "terminate:200",
    ]


async def test_a_failure_after_the_whole_response_left_declares_finished_only_once() -> None:
    journal: list[str] = []

    async def app(_scope: Scope, _receive: Receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send({"type": "http.response.body", "body": b"done", "more_body": False})
        raise RuntimeError("after the fact")

    middleware = RequestLifecycleMiddleware(app, dispatcher=_journalling_dispatcher(journal))

    with pytest.raises(RuntimeError, match="after the fact"):
        await middleware(_http_scope(), _receive, _journalling_send(journal))

    assert journal.count("finish_request") == 1
    assert journal[-1] == "terminate:200"


async def test_a_second_response_start_dispatches_no_second_response_event() -> None:
    journal: list[str] = []

    async def app(_scope: Scope, _receive: Receive, send: Send) -> None:
        start: Message = {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        }
        await send(start)
        await send(dict(start))
        await send({"type": "http.response.body", "body": b"twice", "more_body": False})

    middleware = RequestLifecycleMiddleware(app, dispatcher=_journalling_dispatcher(journal))

    await middleware(_http_scope(), _receive, _journalling_send(journal))

    assert journal.count("response:200") == 1


@pytest.mark.parametrize("scope_type", ["lifespan", "websocket"])
async def test_other_scopes_pass_through_untouched(scope_type: str) -> None:
    journal: list[str] = []
    scope: dict[str, object] = {"type": scope_type}
    seen: list[tuple[object, object, object]] = []

    async def app(inner_scope: Scope, receive: Receive, send: Send) -> None:
        seen.append((inner_scope, receive, send))

    async def send(_message: Message) -> None:
        return None

    middleware = RequestLifecycleMiddleware(app, dispatcher=_journalling_dispatcher(journal))

    await middleware(scope, _receive, send)

    assert seen == [(scope, _receive, send)]
    assert journal == []


@final
class _UnitScopedDispatcher:
    """A dispatcher tracing per unit of work, recording when each unit opens and closes."""

    def __init__(self, journal: list[str]) -> None:
        self._inner = _journalling_dispatcher(journal)
        self._journal = journal

    async def dispatch(self, event: _EventT, event_name: str | type | None = None) -> _EventT:
        return await self._inner.dispatch(event, event_name)

    def begin_unit(self) -> None:
        self._journal.append("begin_unit")

    def end_unit(self) -> None:
        self._journal.append("end_unit")


@final
class _UnitAttributesAsData:
    """A dispatcher whose unit attributes exist but cannot be called."""

    begin_unit: str = "tracing is off"
    end_unit: str = "tracing is off"

    def __init__(self, journal: list[str]) -> None:
        self._inner = _journalling_dispatcher(journal)

    async def dispatch(self, event: _EventT, event_name: str | type | None = None) -> _EventT:
        return await self._inner.dispatch(event, event_name)


async def test_a_unit_scoped_dispatcher_frames_the_whole_request() -> None:
    journal: list[str] = []
    middleware = RequestLifecycleMiddleware(
        _answering_app(b"traced"), dispatcher=_UnitScopedDispatcher(journal)
    )

    await middleware(_http_scope(), _receive, _journalling_send(journal))

    assert journal[0] == "begin_unit"
    assert journal[-1] == "end_unit"
    assert journal[-2] == "terminate:200"


async def test_unit_attributes_that_cannot_be_called_are_left_alone() -> None:
    journal: list[str] = []
    middleware = RequestLifecycleMiddleware(
        _answering_app(b"plain"), dispatcher=_UnitAttributesAsData(journal)
    )

    await middleware(_http_scope(), _receive, _journalling_send(journal))

    assert "begin_unit" not in journal
    assert journal[0] == "request"
    assert journal[-1] == "terminate:200"
