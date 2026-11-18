"""A profile token holds characters a profile is never stored under."""

from __future__ import annotations

from .http_kernel_error import HttpKernelError

__all__ = ["InvalidTokenError"]


class InvalidTokenError(HttpKernelError, ValueError):
    """A profile token holds characters a profile is never stored under.

    A token names a file under the profiler's folder, so anything but letters,
    digits, ``_`` and ``-`` is refused before a path is built from it — a
    ``..`` reaching outside the folder included. Also a :class:`ValueError`.

    Attributes:
        token: The token that was refused.
    """

    token: str

    def __init__(self, token: str) -> None:
        """Record the refused token."""
        self.token = token
        super().__init__(
            f"profile token {token!r} is not valid: only letters, digits, '_' and '-' are allowed"
        )
