"""The rate limit that speaks for a response, out of every one a request consumed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from starlette.requests import Request
    from xtr_rate_limiter import RateLimit

__all__ = ["STATE_KEY", "AppliedRateLimit", "applied_rate_limit"]

STATE_KEY: Final = "_xtr_rate_limit"
"""Where a request keeps the limit its response reports, on ``request.state``."""


@final
@dataclass(frozen=True, slots=True)
class AppliedRateLimit:
    """A consumed limit, and how many tokens each call of its route takes.

    Attributes:
        rate_limit: The limit as the request left it.
        tokens: The tokens one call consumes.
    """

    rate_limit: RateLimit
    tokens: int

    @property
    def remaining_calls(self) -> float:
        """The calls left, rather than the tokens."""
        return self.rate_limit.remaining_tokens / self.tokens


def applied_rate_limit(request: Request) -> AppliedRateLimit | None:
    """Return the limit ``request``'s response reports; ``None`` when there is none."""
    applied: object = getattr(request.state, STATE_KEY, None)
    return applied if isinstance(applied, AppliedRateLimit) else None
