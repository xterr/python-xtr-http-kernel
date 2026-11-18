"""A profile was asked for data no collector of it gathered."""

from __future__ import annotations

from .http_kernel_error import HttpKernelError

__all__ = ["UnknownCollectorError"]


class UnknownCollectorError(HttpKernelError, LookupError):
    """A profile was asked for data no collector of it gathered.

    Also a :class:`LookupError`, as a missing key is.

    Attributes:
        name: The collector asked for.
        available: The collectors the profile holds.
    """

    name: str
    available: tuple[str, ...]

    def __init__(self, name: str, available: tuple[str, ...]) -> None:
        """Record the collector asked for and the ones there are."""
        self.name = name
        self.available = available
        known = ", ".join(f'"{collector}"' for collector in available) or "none"
        super().__init__(f'collector "{name}" does not exist; the profile holds: {known}')
