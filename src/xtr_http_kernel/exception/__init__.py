"""Every error this library raises.

All of them derive from :class:`HttpKernelError`, so one ``except`` catches
anything the request lifecycle can go wrong with, and a narrower one handles
one cause. Each carries the data a caller needs as typed attributes rather
than forcing a message to be parsed.
"""

from __future__ import annotations

from .http_kernel_error import HttpKernelError
from .invalid_middleware_priority_error import InvalidMiddlewarePriorityError

__all__ = ["HttpKernelError", "InvalidMiddlewarePriorityError"]
