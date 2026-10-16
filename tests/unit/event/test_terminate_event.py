"""Unit tests for :class:`xtr_http_kernel.event.TerminateEvent`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.event import TerminateEvent

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from xtr_http_message_contracts import ServerRequestInterface


def test_it_carries_the_request_the_state_and_the_status_that_was_sent(
    server_request: ServerRequestInterface,
    state: MutableMapping[str, object],
) -> None:
    event = TerminateEvent(server_request, state, 204)

    assert event.request is server_request
    assert event.state is state
    assert event.status_code == 204


def test_a_failure_that_sent_nothing_terminates_at_five_hundred(
    server_request: ServerRequestInterface,
    state: MutableMapping[str, object],
) -> None:
    event = TerminateEvent(server_request, state, 500)

    assert event.status_code == 500
