"""Unit tests for :class:`xtr_http_kernel.event_listener.DisallowSearchIndexingListener`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.datastructures import MutableHeaders

from xtr_http_kernel.event import ResponseEvent
from xtr_http_kernel.event_listener import DisallowSearchIndexingListener

if TYPE_CHECKING:
    from starlette.requests import Request


def test_enabled_marks_the_response_noindex(http_request: Request) -> None:
    headers = MutableHeaders()

    DisallowSearchIndexingListener(enabled=True).on_response(
        ResponseEvent(http_request, 200, headers)
    )

    assert headers["X-Robots-Tag"] == "noindex"


def test_disabled_leaves_the_response_alone(http_request: Request) -> None:
    headers = MutableHeaders()

    DisallowSearchIndexingListener(enabled=False).on_response(
        ResponseEvent(http_request, 200, headers)
    )

    assert "X-Robots-Tag" not in headers
