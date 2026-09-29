"""Unit tests for the listener writing the ``X-RateLimit-*`` headers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from starlette.datastructures import MutableHeaders
from xtr_rate_limiter import RateLimit

from xtr_http_kernel.event import ResponseEvent
from xtr_http_kernel.event_listener.rate_limit_headers_listener import RateLimitHeadersListener
from xtr_http_kernel.rate_limiter._applied_rate_limit import STATE_KEY, AppliedRateLimit

if TYPE_CHECKING:
    from starlette.requests import Request

_RESET = datetime(2026, 1, 1, tzinfo=UTC)


def _apply(request: Request, *, remaining: int = 3, tokens: int = 1, reset: bool = True) -> None:
    limit = RateLimit(
        remaining, _RESET, accepted=True, limit=10, reset_at=_RESET if reset else None
    )
    setattr(request.state, STATE_KEY, AppliedRateLimit(limit, tokens))


def _respond(request: Request, headers: MutableHeaders | None = None) -> MutableHeaders:
    outgoing = headers if headers is not None else MutableHeaders()
    RateLimitHeadersListener().on_response(ResponseEvent(request, 200, outgoing))
    return outgoing


def test_it_reports_the_applied_limit_in_calls(http_request: Request) -> None:
    _apply(http_request, remaining=5, tokens=2)

    headers = _respond(http_request)

    assert headers["x-ratelimit-limit"] == "5"
    assert headers["x-ratelimit-remaining"] == "2"
    assert headers["x-ratelimit-reset"] == str(int(_RESET.timestamp()))
    assert headers["cache-control"] == "private"


def test_it_leaves_a_request_without_a_limit_alone(http_request: Request) -> None:
    assert "x-ratelimit-limit" not in _respond(http_request)


def test_it_leaves_a_limit_without_a_reset_alone(http_request: Request) -> None:
    _apply(http_request, reset=False)

    assert "x-ratelimit-limit" not in _respond(http_request)


def test_a_response_reporting_its_own_limit_keeps_it(http_request: Request) -> None:
    _apply(http_request)

    headers = _respond(http_request, MutableHeaders({"X-RateLimit-Remaining": "99"}))

    assert headers["x-ratelimit-remaining"] == "99"
    assert "x-ratelimit-limit" not in headers


@pytest.mark.parametrize(
    ("cache_control", "expected"),
    [
        ("public, max-age=60", "max-age=60, private"),
        ("no-store", "no-store"),
        ("private, max-age=5", "private, max-age=5"),
    ],
)
def test_a_counted_response_is_never_shared(
    http_request: Request, cache_control: str, expected: str
) -> None:
    _apply(http_request)

    headers = _respond(http_request, MutableHeaders({"cache-control": cache_control}))

    assert headers["cache-control"] == expected
