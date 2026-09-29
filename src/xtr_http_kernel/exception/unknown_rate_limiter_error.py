"""A route names a rate limiter nobody configured."""

from __future__ import annotations

from .http_kernel_error import HttpKernelError

__all__ = ["UnknownRateLimiterError"]


class UnknownRateLimiterError(HttpKernelError, LookupError):
    """A route names a rate limiter nobody configured.

    Raised when the first request reaches the route, since routes are
    declared before any kernel is built. A limiter is configured in the
    rate limiter bundle's configuration, under the name the route uses.

    Attributes:
        limiter: The name the route used.
        available: The names the application configured.
    """

    limiter: str
    available: tuple[str, ...]

    def __init__(self, limiter: str, available: tuple[str, ...]) -> None:
        """Record the unknown name and the ones that exist."""
        self.limiter = limiter
        self.available = available
        names = '", "'.join(available)
        known = f'"{names}"' if available else "none"
        super().__init__(
            f'Rate limiter "{limiter}" does not exist. Did you forget to configure it? '
            f"Available limiters: {known}.",
        )
