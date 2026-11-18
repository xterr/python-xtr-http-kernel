from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from starlette.routing import Mount, Route

from xtr_http_kernel.profiler.route_recording_middleware import RouteRecordingMiddleware

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

pytestmark = pytest.mark.anyio


async def _endpoint(scope: Scope, receive: Receive, send: Send) -> None:
    del scope, receive, send


def _answering(route: object) -> ASGIApp:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        del receive
        scope["route"] = route
        scope["path_params"] = {"isbn": 42}
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    return app


async def _run(route: object, scope_type: str = "http") -> Scope:
    scope: Scope = {"type": scope_type}
    sent: list[Message] = []

    async def receive() -> Message:
        return {"type": "http.request"}

    async def send(message: Message) -> None:
        sent.append(message)

    await RouteRecordingMiddleware(_answering(route))(scope, receive, send)
    assert sent
    return scope


async def test_a_matched_route_is_noted_as_the_response_starts() -> None:
    route = Route("/books/{isbn}", _endpoint, name="show_book", methods=["GET"])

    scope = await _run(route)

    noted = cast("dict[str, object]", scope["state"])["_profiler.route"]
    assert noted == {
        "matched": True,
        "path_params": {"isbn": "42"},
        "name": "show_book",
        "path": "/books/{isbn}",
        "methods": ["GET", "HEAD"],
        "endpoint": f"{__name__}._endpoint",
    }


async def test_a_route_of_another_kind_is_noted_by_name() -> None:
    scope = await _run(Mount("/static", app=_endpoint, name="static"))

    noted = cast("dict[str, object]", scope["state"])["_profiler.route"]
    assert noted == {"matched": True, "path_params": {"isbn": "42"}, "name": "static"}


async def test_no_route_is_noted_as_unmatched() -> None:
    scope = await _run(None)

    noted = cast("dict[str, object]", scope["state"])["_profiler.route"]
    assert noted == {"matched": False, "path_params": {"isbn": "42"}}


async def test_a_connection_that_is_not_a_request_passes_through() -> None:
    scope = await _run(None, scope_type="websocket")

    assert "state" not in scope
