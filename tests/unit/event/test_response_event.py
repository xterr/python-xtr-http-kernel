"""Unit tests for :class:`xtr_http_kernel.event.ResponseEvent`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.datastructures import MutableHeaders

from xtr_http_kernel.event import ResponseEvent

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from xtr_http_message_contracts import ServerRequestInterface


def test_it_carries_the_request_the_state_and_what_the_response_starts_with(
    server_request: ServerRequestInterface,
    state: MutableMapping[str, object],
) -> None:
    event = ResponseEvent(
        server_request,
        state,
        200,
        MutableHeaders(raw=[(b"content-type", b"application/json")]),
    )

    assert event.request is server_request
    assert event.state is state
    assert event.status_code == 200
    assert event.headers["content-type"] == "application/json"


def test_a_listener_may_replace_the_status_code(
    server_request: ServerRequestInterface,
    state: MutableMapping[str, object],
) -> None:
    event = ResponseEvent(server_request, state, 200, MutableHeaders(raw=[]))

    event.status_code = 503

    assert event.status_code == 503


def test_a_header_a_listener_adds_reaches_the_list_the_event_was_given(
    server_request: ServerRequestInterface,
    state: MutableMapping[str, object],
) -> None:
    raw: list[tuple[bytes, bytes]] = [(b"content-type", b"text/plain")]
    event = ResponseEvent(server_request, state, 200, MutableHeaders(raw=raw))

    event.headers["x-request-id"] = "0198f2c1"
    del event.headers["content-type"]

    assert raw == [(b"x-request-id", b"0198f2c1")]


def test_it_offers_no_way_to_replace_the_body(
    server_request: ServerRequestInterface,
    state: MutableMapping[str, object],
) -> None:
    event = ResponseEvent(server_request, state, 200, MutableHeaders(raw=[]))

    assert not hasattr(event, "body")
    assert not hasattr(event, "set_body")
    assert not hasattr(event, "response")
    assert not hasattr(event, "set_response")
