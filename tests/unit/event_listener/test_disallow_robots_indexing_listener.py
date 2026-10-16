"""Unit tests for :class:`xtr_http_kernel.event_listener.DisallowRobotsIndexingListener`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.datastructures import MutableHeaders

from xtr_http_kernel.event import ResponseEvent
from xtr_http_kernel.event_listener import DisallowRobotsIndexingListener

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from xtr_http_message_contracts import ServerRequestInterface


def test_enabled_marks_the_response_noindex(
    server_request: ServerRequestInterface,
    state: MutableMapping[str, object],
) -> None:
    headers = MutableHeaders()

    DisallowRobotsIndexingListener(enabled=True).on_response(
        ResponseEvent(server_request, state, 200, headers)
    )

    assert headers["X-Robots-Tag"] == "noindex"


def test_disabled_leaves_the_response_alone(
    server_request: ServerRequestInterface,
    state: MutableMapping[str, object],
) -> None:
    headers = MutableHeaders()

    DisallowRobotsIndexingListener(enabled=False).on_response(
        ResponseEvent(server_request, state, 200, headers)
    )

    assert "X-Robots-Tag" not in headers
