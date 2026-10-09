"""A cookie of a request message cannot be written into a ``Cookie`` header."""

from __future__ import annotations

from .http_kernel_error import HttpKernelError

__all__ = ["InvalidCookieError"]


class InvalidCookieError(HttpKernelError, ValueError):
    """A cookie of a request message is not one a ``Cookie`` header can carry.

    The cookies of a message are a plain mapping, which nothing checked on
    the way in; the header they are written into is read back by splitting it
    apart again. So a name or a value the cookie grammar refuses would either
    break the header or come back as something else — a value holding ``;``
    reads back as further cookies of its own, one of them possibly replacing
    a cookie that was really sent. The cookie is refused here instead, where
    the name is still known.

    Also a :class:`ValueError`, so code that already guards what it builds
    with ``except ValueError`` keeps working without learning a new
    exception.

    Attributes:
        name: The name the cookie was held under.
        reason: What is wrong with the cookie.
    """

    name: str
    reason: str

    def __init__(self, name: str, reason: str) -> None:
        """Record which cookie was refused and why."""
        self.name = name
        self.reason = reason
        super().__init__(f'The "{name}" cookie cannot go into a Cookie header: {reason}')
