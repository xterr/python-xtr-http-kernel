"""A data collector tag's priority is not an integer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .http_kernel_error import HttpKernelError

if TYPE_CHECKING:
    from xtr_dependency_injection import ServiceKey

__all__ = ["InvalidCollectorPriorityError"]


class InvalidCollectorPriorityError(HttpKernelError, TypeError):
    """A data collector tag's ``priority`` is not an integer.

    The priority orders the panels of a profile, so a value that cannot be
    compared with the others fails the build rather than a profile later.
    Also a :class:`TypeError`.

    Attributes:
        key: The tagged definition.
        priority: The value it carried.
    """

    key: ServiceKey
    priority: object

    def __init__(self, key: ServiceKey, priority: object) -> None:
        """Record the definition and the priority it carried."""
        self.key = key
        self.priority = priority
        super().__init__(
            f"the data collector {key!r} has a priority of {priority!r}; it must be an integer"
        )
