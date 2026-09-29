"""Unit tests for the errors a rate-limited route raises."""

from __future__ import annotations

from datetime import UTC, datetime

from starlette.exceptions import HTTPException
from xtr_rate_limiter import RateLimit

from xtr_http_kernel.exception import (
    HttpKernelError,
    InvalidRateLimitError,
    TooManyRequestsError,
    UnknownRateLimiterError,
)


def test_too_many_requests_is_a_429_with_whole_seconds_to_wait() -> None:
    retry = datetime(2026, 1, 1, 0, 0, 30, tzinfo=UTC)
    limit = RateLimit(0, retry, accepted=False, limit=5)

    error = TooManyRequestsError(limit, "api", "alice", retry.timestamp() - 12.5)

    assert isinstance(error, HttpKernelError)
    assert isinstance(error, HTTPException)
    assert error.status_code == 429
    assert error.retry_after == 13
    assert error.headers == {"Retry-After": "13"}
    assert (error.rate_limit, error.limiter, error.key) == (limit, "api", "alice")


def test_too_many_requests_never_waits_a_negative_time() -> None:
    retry = datetime(2026, 1, 1, tzinfo=UTC)
    limit = RateLimit(0, retry, accepted=False, limit=5)

    assert TooManyRequestsError(limit, "api", "k", retry.timestamp() + 5).retry_after == 0


def test_an_unknown_limiter_names_the_ones_that_exist() -> None:
    known = UnknownRateLimiterError("apo", ("api", "login"))
    none = UnknownRateLimiterError("api", ())

    assert isinstance(known, LookupError)
    assert 'Available limiters: "api", "login".' in str(known)
    assert "Available limiters: none." in str(none)


def test_an_invalid_rate_limit_carries_its_reason() -> None:
    error = InvalidRateLimitError("bad")

    assert isinstance(error, ValueError)
    assert error.reason == "bad"
