"""Every error this library raises.

All of them derive from :class:`HttpKernelError`, so one ``except`` catches
anything the request lifecycle can go wrong with, and a narrower one handles
one cause. Each carries the data a caller needs as typed attributes rather
than forcing a message to be parsed.
"""

from __future__ import annotations

from .http_kernel_error import HttpKernelError
from .invalid_argument_error import InvalidArgumentError
from .invalid_cookie_error import InvalidCookieError
from .invalid_middleware_priority_error import InvalidMiddlewarePriorityError
from .invalid_rate_limit_error import InvalidRateLimitError
from .ranged_response_body_error import RangedResponseBodyError
from .streamed_response_body_error import StreamedResponseBodyError
from .too_many_requests_error import TooManyRequestsError
from .unknown_rate_limiter_error import UnknownRateLimiterError
from .unsupported_connection_error import UnsupportedConnectionError

__all__ = [
    "HttpKernelError",
    "InvalidArgumentError",
    "InvalidCookieError",
    "InvalidMiddlewarePriorityError",
    "InvalidRateLimitError",
    "RangedResponseBodyError",
    "StreamedResponseBodyError",
    "TooManyRequestsError",
    "UnknownRateLimiterError",
    "UnsupportedConnectionError",
]
