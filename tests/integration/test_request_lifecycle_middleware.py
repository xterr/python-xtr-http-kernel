"""The lifecycle middleware on a FastAPI application, driven as a client would.

Requests go straight at the application through an ASGI transport, so the
suite never binds a socket. ``raise_app_exceptions=False`` lets the framework
answer an unhandled failure with its 500 instead of re-raising it into the
test after the response.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, cast

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from starlette.responses import PlainTextResponse, StreamingResponse
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
    from collections.abc import AsyncIterator

    from starlette.types import ASGIApp, Message, Receive, Scope, Send

pytestmark = pytest.mark.anyio

_UNIT: ContextVar[str] = ContextVar("request_lifecycle_test_unit", default="unset")


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


def _application(dispatcher: EventDispatcher) -> FastAPI:
    app = FastAPI()

    @app.get("/ok")
    async def ok() -> PlainTextResponse:
        return PlainTextResponse("all good")

    @app.get("/missing")
    async def missing() -> PlainTextResponse:
        raise HTTPException(status_code=404)

    @app.get("/boom")
    async def boom() -> PlainTextResponse:
        raise RuntimeError("boom")

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        async def chunks() -> AsyncIterator[bytes]:
            yield b"alpha"
            yield b"beta"
            yield b"gamma"

        return StreamingResponse(chunks(), media_type="text/plain")

    @app.get("/unit/async")
    async def unit_seen_async() -> PlainTextResponse:
        return PlainTextResponse(_UNIT.get())

    @app.get("/unit/sync")
    def unit_seen_sync() -> PlainTextResponse:
        return PlainTextResponse(_UNIT.get())

    app.add_middleware(RequestLifecycleMiddleware, dispatcher=dispatcher)
    return app


def _client(app: ASGIApp) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://bookshop.test")


async def test_a_successful_request_dispatches_the_whole_lifecycle_in_order() -> None:
    journal: list[str] = []
    async with _client(_application(_journalling_dispatcher(journal))) as client:
        response = await client.get("/ok")

    assert response.status_code == 200
    assert response.text == "all good"
    assert journal == ["request", "response:200", "finish_request", "terminate:200"]


async def test_a_request_listener_answer_short_circuits_the_endpoint() -> None:
    journal: list[str] = []
    dispatcher = _journalling_dispatcher(journal)

    async def answer(event: RequestEvent) -> None:
        journal.append("short-circuit")
        event.set_response(PlainTextResponse("down for maintenance", status_code=503))

    dispatcher.add_listener(RequestEvent, answer, priority=100)
    async with _client(_application(dispatcher)) as client:
        response = await client.get("/ok")

    assert response.status_code == 503
    assert response.text == "down for maintenance"
    assert journal == ["short-circuit", "response:503", "finish_request", "terminate:503"]


async def test_an_http_exception_is_already_a_response_when_it_reaches_the_lifecycle() -> None:
    journal: list[str] = []
    async with _client(_application(_journalling_dispatcher(journal))) as client:
        response = await client.get("/missing")

    assert response.status_code == 404
    assert journal == ["request", "response:404", "finish_request", "terminate:404"]


async def test_an_unhandled_failure_is_announced_before_the_framework_answers_500() -> None:
    journal: list[str] = []
    async with _client(_application(_journalling_dispatcher(journal))) as client:
        response = await client.get("/boom")

    assert response.status_code == 500
    assert journal == ["request", "exception:RuntimeError", "finish_request", "terminate:500"]


async def test_an_exception_listener_answer_reaches_the_client_instead_of_a_500() -> None:
    journal: list[str] = []
    dispatcher = _journalling_dispatcher(journal)

    async def answer(event: ExceptionEvent) -> None:
        event.set_response(PlainTextResponse("mended", status_code=503))

    dispatcher.add_listener(ExceptionEvent, answer, priority=-100)
    async with _client(_application(dispatcher)) as client:
        response = await client.get("/boom")

    assert response.status_code == 503
    assert response.text == "mended"
    assert journal == [
        "request",
        "exception:RuntimeError",
        "response:503",
        "finish_request",
        "terminate:503",
    ]


async def test_a_header_added_at_the_response_event_reaches_the_client() -> None:
    journal: list[str] = []
    dispatcher = _journalling_dispatcher(journal)

    async def stamp(event: ResponseEvent) -> None:
        event.headers["x-request-id"] = "42"

    dispatcher.add_listener(ResponseEvent, stamp)
    async with _client(_application(dispatcher)) as client:
        response = await client.get("/ok")

    assert response.headers["x-request-id"] == "42"


async def test_a_streamed_body_finishes_before_its_last_chunk_and_terminates_after() -> None:
    journal: list[str] = []
    app = _application(_journalling_dispatcher(journal))

    async def recording(scope: Scope, receive: Receive, send: Send) -> None:
        async def recording_send(message: Message) -> None:
            if cast("str", message["type"]) == "http.response.body":
                body = cast("bytes", message.get("body", b""))
                journal.append(f"sent:{body.decode()}")
            await send(message)

        await app(scope, receive, recording_send)

    async with _client(recording) as client:
        response = await client.get("/stream")

    assert response.text == "alphabetagamma"
    assert journal == [
        "request",
        "response:200",
        "sent:alpha",
        "sent:beta",
        "sent:gamma",
        "finish_request",
        "sent:",
        "terminate:200",
    ]


@pytest.mark.parametrize("path", ["/unit/async", "/unit/sync"])
async def test_a_value_set_at_the_request_event_is_seen_all_the_way_down(path: str) -> None:
    journal: list[str] = []
    dispatcher = _journalling_dispatcher(journal)

    async def open_unit(event: RequestEvent) -> None:
        # Listeners run inline in the caller's task, so what this one sets is
        # the context the endpoint — async, or sync in a copied context on a
        # worker thread — and the terminate listener run in.
        _ = _UNIT.set(f"unit-of{event.request.url.path}")

    async def close_unit(_event: TerminateEvent) -> None:
        journal.append(f"terminate saw {_UNIT.get()}")

    dispatcher.add_listener(RequestEvent, open_unit)
    dispatcher.add_listener(TerminateEvent, close_unit)
    async with _client(_application(dispatcher)) as client:
        response = await client.get(path)

    assert response.text == f"unit-of{path}"
    assert f"terminate saw unit-of{path}" in journal
