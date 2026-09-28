"""The tag a bundle puts on the middleware factories it contributes.

A definition tagged this way provides a middleware factory — a callable
taking the downstream ASGI app and returning the app wrapped. The
http_kernel bundle collects every tagged definition when the kernel is
built and orders them into the
:class:`~xtr_http_kernel.middleware_stack.MiddlewareStack` by the tag's
integer ``priority`` attribute (0 when absent): the highest priority sits
outermost, so it sees the request first.
"""

from __future__ import annotations

from typing import Final

__all__ = ["MIDDLEWARE_TAG"]

MIDDLEWARE_TAG: Final = "http_kernel.middleware"
"""The tag name bundles and the setup call agree on."""
