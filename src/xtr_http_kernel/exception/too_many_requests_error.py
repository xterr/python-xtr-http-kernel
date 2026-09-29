"""A route turned a request away because a rate limit refused it."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final

from starlette.exceptions import HTTPException

from .http_kernel_error import HttpKernelError

if TYPE_CHECKING:
    from xtr_rate_limiter import RateLimit

__all__ = ["TooManyRequestsError"]

_TOO_MANY_REQUESTS: Final = 429


class TooManyRequestsError(HttpKernelError, HTTPException):  # pyright: ignore[reportUnsafeMultipleInheritance] -- HttpKernelError adds no __init__; HTTPException's is called below
    """A route turned a request away because a rate limit refused it.

    Also the framework's own HTTP exception, so the application answers it
    as it answers any other: ``429 Too Many Requests`` with a ``Retry-After``
    header, reshaped by an exception handler registered for this class when
    the application wants another body.

    Attributes:
        rate_limit: The limit that refused the request.
        limiter: The configured limiter's name.
        key: The key the request was counted under.
        retry_after: Whole seconds until the request would be accepted.
    """

    rate_limit: RateLimit
    limiter: str
    key: str
    retry_after: int

    def __init__(self, rate_limit: RateLimit, limiter: str, key: str, now: float) -> None:
        """Record the refused limit, counting the wait from ``now``."""
        self.rate_limit = rate_limit
        self.limiter = limiter
        self.key = key
        self.retry_after = max(0, math.ceil(rate_limit.retry_after.timestamp() - now))
        HTTPException.__init__(
            self,
            _TOO_MANY_REQUESTS,
            headers={"Retry-After": str(self.retry_after)},
        )
