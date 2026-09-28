"""The tag a bundle puts on the middleware factories it contributes.

A definition tagged this way provides a middleware factory — a callable
taking the downstream ASGI app and returning the app wrapped. The setup
call collects every tagged factory when the application's lifespan starts
and composes the chain each request runs through. A factory advertises its
place with an integer ``priority`` attribute (0 when absent): the highest
priority sits outermost, so it sees the request first.
"""

from __future__ import annotations

from typing import Final

__all__ = ["MIDDLEWARE_TAG"]

MIDDLEWARE_TAG: Final = "http_kernel.middleware"
"""The tag name bundles and the setup call agree on."""
