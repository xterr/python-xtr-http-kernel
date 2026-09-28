"""Unit tests for :class:`xtr_http_kernel.event_listener.log_unit_listener.LogUnitListener`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_logging import end_unit, unit_state

from xtr_http_kernel.event import RequestEvent, TerminateEvent
from xtr_http_kernel.event_listener.log_unit_listener import LogUnitListener

if TYPE_CHECKING:
    from collections.abc import Generator

    from starlette.requests import Request


@pytest.fixture(autouse=True)
def _close_any_unit() -> Generator[None, None, None]:
    yield
    end_unit()


def _fresh() -> list[str]:
    return []


def test_the_request_opens_a_unit_of_work(http_request: Request) -> None:
    listener = LogUnitListener()

    listener.on_request(RequestEvent(http_request))

    assert unit_state(listener, _fresh) is not None


def test_terminate_closes_the_unit(http_request: Request) -> None:
    listener = LogUnitListener()
    listener.on_request(RequestEvent(http_request))
    ended: list[str] = []

    def _ended(state: list[str]) -> None:
        del state
        ended.append("ended")

    _ = unit_state(listener, _fresh, on_end=_ended)

    listener.on_terminate(TerminateEvent(http_request, 200))

    assert ended == ["ended"]
    assert unit_state(listener, _fresh) is None


def test_a_fresh_request_replaces_a_leaked_unit(http_request: Request) -> None:
    listener = LogUnitListener()
    listener.on_request(RequestEvent(http_request))
    first = unit_state(listener, _fresh)

    listener.on_request(RequestEvent(http_request))

    assert unit_state(listener, _fresh) is not first
