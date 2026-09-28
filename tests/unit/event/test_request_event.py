"""Unit tests for :class:`xtr_http_kernel.event.RequestEvent`."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import PlainTextResponse

from xtr_http_kernel.event import RequestEvent


def test_it_carries_the_request_it_was_built_from(http_request: Request) -> None:
    event = RequestEvent(http_request)

    assert event.request is http_request
    assert event.request.url.path == "/books/978-0141439518"


def test_a_request_nobody_answered_carries_no_response(http_request: Request) -> None:
    event = RequestEvent(http_request)

    assert event.has_response() is False
    assert event.response is None
    assert event.is_propagation_stopped() is False


def test_answering_the_request_stops_the_listeners_after_it(http_request: Request) -> None:
    event = RequestEvent(http_request)
    response = PlainTextResponse("cached")

    event.set_response(response)

    assert event.has_response() is True
    assert event.response is response
    assert event.is_propagation_stopped() is True


def test_the_last_listener_to_answer_wins(http_request: Request) -> None:
    event = RequestEvent(http_request)
    last = PlainTextResponse("last")

    event.set_response(PlainTextResponse("first"))
    event.set_response(last)

    assert event.response is last
