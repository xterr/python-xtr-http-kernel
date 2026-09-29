"""The lifecycle or its configuration was given a value it cannot work with."""

from __future__ import annotations

from .http_kernel_error import HttpKernelError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(HttpKernelError, ValueError):
    """The lifecycle or its configuration was given a value it cannot work with.

    Also a :class:`ValueError`, so code that already guards its configuration
    with ``except ValueError`` keeps working without learning a new exception.

    Attributes:
        reason: What is wrong with the value.
    """

    reason: str

    def __init__(self, reason: str) -> None:
        """Record what is wrong with the value."""
        self.reason = reason
        super().__init__(reason)
