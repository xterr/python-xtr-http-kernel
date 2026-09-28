"""Unit tests for :class:`xtr_http_kernel.event.ExceptionEvent`."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import PlainTextResponse

from xtr_http_kernel.event import ExceptionEvent


def test_it_carries_the_request_and_what_was_raised(http_request: Request) -> None:
    raised = RuntimeError("the catalog is down")

    event = ExceptionEvent(http_request, raised)

    assert event.request is http_request
    assert event.exception is raised


def test_an_exception_nobody_converted_carries_no_response(http_request: Request) -> None:
    event = ExceptionEvent(http_request, RuntimeError("boom"))

    assert event.has_response() is False
    assert event.response is None
    assert event.is_propagation_stopped() is False


def test_converting_the_exception_stops_the_listeners_after_it(http_request: Request) -> None:
    event = ExceptionEvent(http_request, RuntimeError("boom"))
    response = PlainTextResponse("service unavailable", status_code=503)

    event.set_response(response)

    assert event.has_response() is True
    assert event.response is response
    assert event.is_propagation_stopped() is True


def test_it_carries_what_an_except_clause_would_not_catch(http_request: Request) -> None:
    # A cancellation derives from BaseException, and a listener logging the
    # failure still wants to see it.
    raised = KeyboardInterrupt()

    event = ExceptionEvent(http_request, raised)

    assert event.exception is raised
