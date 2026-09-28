"""Raised when a middleware tag carries a priority that is not an integer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .http_kernel_error import HttpKernelError

if TYPE_CHECKING:
    from collections.abc import Hashable

__all__ = ["InvalidMiddlewarePriorityError"]


class InvalidMiddlewarePriorityError(HttpKernelError):
    """A ``http_kernel.middleware`` tag's ``priority`` attribute is not an integer.

    Raised while the kernel is built, so a misdeclared bundle fails at
    startup rather than serving an unordered chain.

    Attributes:
        key: The tagged service's ``(type, qualifier)`` key.
        priority: What the tag carried instead of an integer.
    """

    key: tuple[type, Hashable | None]
    priority: object

    def __init__(self, key: tuple[type, Hashable | None], priority: object) -> None:
        """Record the offending service key and what its tag carried."""
        self.key = key
        self.priority = priority
        provided, qualifier = key
        name = f"{provided.__module__}.{provided.__qualname__}"
        service = name if qualifier is None else f"{name}[{qualifier!r}]"
        super().__init__(
            f"the http_kernel.middleware tag on {service} must carry an integer priority, "
            f"not {priority!r}"
        )
