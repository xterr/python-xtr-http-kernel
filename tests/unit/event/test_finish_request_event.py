"""Unit tests for :class:`xtr_http_kernel.event.FinishRequestEvent`."""

from __future__ import annotations

from starlette.requests import Request

from xtr_http_kernel.event import FinishRequestEvent


def test_it_carries_the_request_whose_handling_finished(http_request: Request) -> None:
    event = FinishRequestEvent(http_request)

    assert event.request is http_request


def test_a_listener_may_stop_the_ones_after_it(http_request: Request) -> None:
    event = FinishRequestEvent(http_request)

    event.stop_propagation()

    assert event.is_propagation_stopped() is True
