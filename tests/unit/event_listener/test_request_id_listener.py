"""Unit tests for :class:`xtr_http_kernel.event_listener.RequestIdListener`."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

import pytest
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from xtr_logging import clear_context, current_context

from xtr_http_kernel.event import RequestEvent, ResponseEvent
from xtr_http_kernel.event_listener import RequestIdListener

if TYPE_CHECKING:
    from collections.abc import Generator

HEX_32 = re.compile(r"^[0-9a-f]{32}$")


def _settled_id(request: Request) -> str:
    return cast("str", request.state.request_id)


@pytest.fixture(autouse=True)
def _clean_context() -> Generator[None, None, None]:
    yield
    clear_context()


def _request(request_id: str | None = None) -> Request:
    headers = [(b"host", b"served.test")]
    if request_id is not None:
        headers.append((b"x-request-id", request_id.encode("latin-1")))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "query_string": b"",
            "headers": headers,
        }
    )


def test_a_valid_incoming_id_is_kept_when_trusted() -> None:
    listener = RequestIdListener()
    event = RequestEvent(_request("trace-1.A_b"))

    listener.on_request(event)

    assert _settled_id(event.request) == "trace-1.A_b"


def test_a_missing_id_is_generated() -> None:
    listener = RequestIdListener()
    event = RequestEvent(_request())

    listener.on_request(event)

    assert HEX_32.match(_settled_id(event.request))


@pytest.mark.parametrize("sent", ["bad id!", "", "a" * 201, "ünicode"])
def test_an_invalid_incoming_id_is_replaced(sent: str) -> None:
    listener = RequestIdListener()
    event = RequestEvent(_request(sent.encode("latin-1", "replace").decode("latin-1")))

    listener.on_request(event)

    assert _settled_id(event.request) != sent
    assert HEX_32.match(_settled_id(event.request))


def test_a_valid_incoming_id_is_replaced_when_not_trusted() -> None:
    listener = RequestIdListener(trust_incoming=False)
    event = RequestEvent(_request("trace-1"))

    listener.on_request(event)

    assert _settled_id(event.request) != "trace-1"
    assert HEX_32.match(_settled_id(event.request))


def test_a_custom_header_is_read() -> None:
    listener = RequestIdListener(header="X-Trace-Id")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "query_string": b"",
            "headers": [(b"x-trace-id", b"trace-9")],
        }
    )
    event = RequestEvent(request)

    listener.on_request(event)

    assert _settled_id(event.request) == "trace-9"


def test_the_id_is_bound_to_the_log_context() -> None:
    listener = RequestIdListener()
    event = RequestEvent(_request("trace-ctx"))

    listener.on_request(event)

    assert current_context()["request_id"] == "trace-ctx"


def test_the_response_echoes_the_request_id() -> None:
    listener = RequestIdListener()
    request = _request("trace-1")
    listener.on_request(RequestEvent(request))
    headers = MutableHeaders()

    listener.on_response(ResponseEvent(request, 200, headers))

    assert headers["X-Request-Id"] == "trace-1"


def test_the_response_is_left_alone_when_the_request_listener_never_ran() -> None:
    # A higher-priority listener answering at RequestEvent stops propagation,
    # so the response can start without the request half having run.
    listener = RequestIdListener()
    headers = MutableHeaders()

    listener.on_response(ResponseEvent(_request(), 200, headers))

    assert "X-Request-Id" not in headers
