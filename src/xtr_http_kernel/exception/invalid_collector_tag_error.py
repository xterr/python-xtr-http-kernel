"""A data collector tag lacks a name or a template."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .http_kernel_error import HttpKernelError

if TYPE_CHECKING:
    from xtr_dependency_injection import ServiceKey

__all__ = ["InvalidCollectorTagError"]


class InvalidCollectorTagError(HttpKernelError, ValueError):
    """A data collector tag lacks a ``name`` or a ``template``, or one is not a string.

    The name is what a profile keeps the collector's data under and the
    template is what shows it, so neither can be left for later. Also a
    :class:`ValueError`.

    Attributes:
        key: The tagged definition.
        attribute: The attribute that is missing or not a string.
    """

    key: ServiceKey
    attribute: str

    def __init__(self, key: ServiceKey, attribute: str) -> None:
        """Record the definition and the attribute it lacks."""
        self.key = key
        self.attribute = attribute
        super().__init__(
            f"the data collector {key!r} needs a non-empty string {attribute!r} on its tag"
        )
