"""The connection being served cannot be built into a request message."""

from __future__ import annotations

from .http_kernel_error import HttpKernelError

__all__ = ["UnsupportedConnectionError"]


class UnsupportedConnectionError(HttpKernelError):
    """Something asked for the request as a message while a socket was served.

    An HTTP message describes a request and the response it earns, so it can
    only be built from an HTTP request. A WebSocket connection has neither a
    method nor a body to read once, and the frames it exchanges are not
    messages of this kind; a route serving one takes the framework's own
    ``websocket`` parameter instead.

    Attributes:
        connection: What the connection being served is, as the server named
            it — ``"websocket"`` where a socket was served.
    """

    connection: str

    def __init__(self, connection: str) -> None:
        """Record what was being served instead of an HTTP request."""
        self.connection = connection
        super().__init__(
            f'The request cannot be built as a message: a "{connection}" connection is '
            f"being served, not an HTTP request. Take the framework's own websocket "
            f"parameter on a socket route.",
        )
