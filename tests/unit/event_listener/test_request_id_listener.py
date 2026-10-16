"""Unit tests for :class:`xtr_http_kernel.event_listener.RequestIdListener`."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

import pytest
from starlette.datastructures import MutableHeaders
from xtr_http_message import ServerRequest
from xtr_logging import clear_context, current_context

from xtr_http_kernel.event import RequestEvent, ResponseEvent
from xtr_http_kernel.event_listener import RequestIdListener

if TYPE_CHECKING:
    from collections.abc import Generator, MutableMapping

    from xtr_http_message_contracts import ServerRequestInterface

HEX_32 = re.compile(r"^[0-9a-f]{32}$")


@pytest.fixture(autouse=True)
def _clean_context() -> Generator[None, None, None]:
    yield
    clear_context()


def _request(request_id: str | None = None) -> ServerRequestInterface:
    headers = {"Host": "served.test"}
    if request_id is not None:
        headers["X-Request-Id"] = request_id
    return ServerRequest("GET", "http://served.test/", headers)


def _settled_id(event: RequestEvent) -> object:
    return event.state["request_id"]


def test_a_valid_incoming_id_is_kept_when_trusted(state: MutableMapping[str, object]) -> None:
    listener = RequestIdListener(trust_incoming=True)
    event = RequestEvent(_request("trace-1.A_b"), state)

    listener.on_request(event)

    assert _settled_id(event) == "trace-1.A_b"


def test_a_missing_id_is_generated(state: MutableMapping[str, object]) -> None:
    listener = RequestIdListener()
    event = RequestEvent(_request(), state)

    listener.on_request(event)

    assert HEX_32.match(cast("str", _settled_id(event)))


@pytest.mark.parametrize("sent", ["bad id!", "", "a" * 201, "ünicode"])
def test_an_invalid_incoming_id_is_replaced(sent: str, state: MutableMapping[str, object]) -> None:
    listener = RequestIdListener(trust_incoming=True)
    event = RequestEvent(_request(sent.encode("latin-1", "replace").decode("latin-1")), state)

    listener.on_request(event)

    assert _settled_id(event) != sent
    assert HEX_32.match(cast("str", _settled_id(event)))


def test_a_valid_incoming_id_is_replaced_unless_it_is_trusted(
    state: MutableMapping[str, object],
) -> None:
    listener = RequestIdListener()
    event = RequestEvent(_request("trace-1"), state)

    listener.on_request(event)

    assert _settled_id(event) != "trace-1"
    assert HEX_32.match(cast("str", _settled_id(event)))


def test_a_custom_header_is_read(state: MutableMapping[str, object]) -> None:
    listener = RequestIdListener(header="X-Trace-Id", trust_incoming=True)
    request = ServerRequest("GET", "http://served.test/", {"X-Trace-Id": "trace-9"})
    event = RequestEvent(request, state)

    listener.on_request(event)

    assert _settled_id(event) == "trace-9"


def test_the_id_is_bound_to_the_log_context(state: MutableMapping[str, object]) -> None:
    listener = RequestIdListener(trust_incoming=True)
    event = RequestEvent(_request("trace-ctx"), state)

    listener.on_request(event)

    assert current_context()["request_id"] == "trace-ctx"


def test_the_response_echoes_the_request_id(state: MutableMapping[str, object]) -> None:
    listener = RequestIdListener(trust_incoming=True)
    request = _request("trace-1")
    listener.on_request(RequestEvent(request, state))
    headers = MutableHeaders()

    listener.on_response(ResponseEvent(request, state, 200, headers))

    assert headers["X-Request-Id"] == "trace-1"


def test_the_response_is_left_alone_when_the_request_listener_never_ran(
    state: MutableMapping[str, object],
) -> None:
    # A higher-priority listener answering at RequestEvent stops propagation,
    # so the response can start without the request half having run.
    listener = RequestIdListener()
    headers = MutableHeaders()

    listener.on_response(ResponseEvent(_request(), state, 200, headers))

    assert "X-Request-Id" not in headers
