"""Limiters kept in this process, so the tests need no cache, lock or server."""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_rate_limiter import LimiterConfig
from xtr_rate_limiter.bundle import RateLimiterConfig


def _window(limit: int) -> LimiterConfig:
    return LimiterConfig(
        "fixed_window", limit=limit, interval="1 minute", storage="in-memory", lock=None
    )


@configure
def rate_limiter() -> RateLimiterConfig:
    return RateLimiterConfig(
        limiters={
            "tight": _window(1),
            "loose": _window(5),
            "pair": _window(4),
            "open": LimiterConfig("no_limit"),
        },
    )
