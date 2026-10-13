"""The route table was given a value it cannot work with."""

from __future__ import annotations

from xtr_http_kernel.exception.invalid_argument_error import (
    InvalidArgumentError as KernelInvalidArgumentError,
)

from .routing_error import RoutingError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(RoutingError, KernelInvalidArgumentError):  # pyright: ignore[reportUnsafeMultipleInheritance] -- RoutingError adds no __init__; the library error's is the one run
    """The route table was given a value it cannot work with.

    Also the library's own ``InvalidArgumentError``, and so a :class:`ValueError`:
    a caller guarding ``setup()`` with either keeps catching a routing refusal.

    Attributes:
        reason: What is wrong with the value.
    """
