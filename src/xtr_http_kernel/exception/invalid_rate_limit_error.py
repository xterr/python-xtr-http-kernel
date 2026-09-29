"""A route's rate limit was declared in a way it cannot be applied."""

from __future__ import annotations

from .http_kernel_error import HttpKernelError

__all__ = ["InvalidRateLimitError"]


class InvalidRateLimitError(HttpKernelError, ValueError):
    """A route's rate limit was declared in a way it cannot be applied.

    Raised where it is declared — fewer than one token, a router that
    already has routes, a key that is not a string — rather than silently
    limiting nothing.

    Attributes:
        reason: What is wrong with the declaration.
    """

    reason: str

    def __init__(self, reason: str) -> None:
        """Record what is wrong with the declaration."""
        self.reason = reason
        super().__init__(reason)
