"""Unit tests for :class:`xtr_http_kernel.event.FinishRequestEvent`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.event import FinishRequestEvent

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from xtr_http_message_contracts import ServerRequestInterface


def test_it_carries_the_request_and_state_whose_handling_finished(
    server_request: ServerRequestInterface,
    state: MutableMapping[str, object],
) -> None:
    event = FinishRequestEvent(server_request, state)

    assert event.request is server_request
    assert event.state is state


def test_a_listener_may_stop_the_ones_after_it(
    server_request: ServerRequestInterface,
    state: MutableMapping[str, object],
) -> None:
    event = FinishRequestEvent(server_request, state)

    event.stop_propagation()

    assert event.is_propagation_stopped() is True
