"""Every refusal the application dispatches, for the tests to read."""

from __future__ import annotations

from typing import Final

from xtr_event_dispatcher import as_event_listener
from xtr_rate_limiter import RateLimitExceededEvent

REFUSED: Final[list[RateLimitExceededEvent]] = []


@as_event_listener()
def record_refusal(event: RateLimitExceededEvent) -> None:
    REFUSED.append(event)
