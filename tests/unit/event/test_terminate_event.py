"""Unit tests for :class:`xtr_http_kernel.event.TerminateEvent`."""

from __future__ import annotations

from starlette.requests import Request

from xtr_http_kernel.event import TerminateEvent


def test_it_carries_the_request_and_the_status_that_was_sent(http_request: Request) -> None:
    event = TerminateEvent(http_request, 204)

    assert event.request is http_request
    assert event.status_code == 204


def test_a_failure_that_sent_nothing_terminates_at_five_hundred(http_request: Request) -> None:
    event = TerminateEvent(http_request, 500)

    assert event.status_code == 500
