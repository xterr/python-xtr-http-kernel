"""The root every routing error derives from."""

from __future__ import annotations

from xtr_http_kernel.exception.http_kernel_error import HttpKernelError

__all__ = ["RoutingError"]


class RoutingError(HttpKernelError):
    """Base class for every error the route table raises.

    Catch this to handle anything arranging routes can go wrong with. It is an
    :class:`~xtr_http_kernel.exception.HttpKernelError` too, so the library's
    one base still catches it.
    """
