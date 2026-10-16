"""Unit tests for :class:`xtr_http_kernel.event.RequestEvent`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.responses import PlainTextResponse

from xtr_http_kernel.event import RequestEvent

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from xtr_http_message_contracts import ServerRequestInterface


def test_it_carries_the_request_and_state_it_was_built_from(
    server_request: ServerRequestInterface,
    state: MutableMapping[str, object],
) -> None:
    event = RequestEvent(server_request, state)

    assert event.request is server_request
    assert event.request.get_uri().get_path() == "/books/978-0141439518"
    assert event.state is state


def test_a_request_nobody_answered_carries_no_response(
    server_request: ServerRequestInterface,
    state: MutableMapping[str, object],
) -> None:
    event = RequestEvent(server_request, state)

    assert event.response is None
    assert event.is_propagation_stopped() is False


def test_answering_the_request_stops_the_listeners_after_it(
    server_request: ServerRequestInterface,
    state: MutableMapping[str, object],
) -> None:
    event = RequestEvent(server_request, state)
    response = PlainTextResponse("cached")

    event.set_response(response)

    assert event.response is response
    assert event.is_propagation_stopped() is True


def test_the_last_listener_to_answer_wins(
    server_request: ServerRequestInterface,
    state: MutableMapping[str, object],
) -> None:
    event = RequestEvent(server_request, state)
    last = PlainTextResponse("last")

    event.set_response(PlainTextResponse("first"))
    event.set_response(last)

    assert event.response is last


def test_the_state_is_shared_with_whatever_else_holds_the_bag(
    server_request: ServerRequestInterface,
    state: MutableMapping[str, object],
) -> None:
    event = RequestEvent(server_request, state)

    event.state["request_id"] = "trace-1"

    assert state["request_id"] == "trace-1"
