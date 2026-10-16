"""Unit tests for :class:`xtr_http_kernel.event.ExceptionEvent`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.responses import PlainTextResponse

from xtr_http_kernel.event import ExceptionEvent

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from xtr_http_message_contracts import ServerRequestInterface


def test_it_carries_the_request_the_state_and_what_was_raised(
    server_request: ServerRequestInterface,
    state: MutableMapping[str, object],
) -> None:
    raised = RuntimeError("the catalog is down")

    event = ExceptionEvent(server_request, state, raised)

    assert event.request is server_request
    assert event.state is state
    assert event.exception is raised


def test_an_exception_nobody_converted_carries_no_response(
    server_request: ServerRequestInterface,
    state: MutableMapping[str, object],
) -> None:
    event = ExceptionEvent(server_request, state, RuntimeError("boom"))

    assert event.response is None
    assert event.is_propagation_stopped() is False


def test_converting_the_exception_stops_the_listeners_after_it(
    server_request: ServerRequestInterface,
    state: MutableMapping[str, object],
) -> None:
    event = ExceptionEvent(server_request, state, RuntimeError("boom"))
    response = PlainTextResponse("service unavailable", status_code=503)

    event.set_response(response)

    assert event.response is response
    assert event.is_propagation_stopped() is True


def test_it_carries_what_an_except_clause_would_not_catch(
    server_request: ServerRequestInterface,
    state: MutableMapping[str, object],
) -> None:
    # A cancellation derives from BaseException, and a listener logging the
    # failure still wants to see it.
    raised = KeyboardInterrupt()

    event = ExceptionEvent(server_request, state, raised)

    assert event.exception is raised
