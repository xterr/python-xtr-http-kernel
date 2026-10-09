"""Requests built straight from a connection, the way a server hands one over.

The suite never binds a socket, so a request under test is built from the
scope and the body a server would have produced.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.requests import Request

if TYPE_CHECKING:
    from collections.abc import Iterable

    from starlette.types import Message, Receive

__all__ = ["asgi_request", "asgi_scope", "received"]


def received(body: bytes) -> Receive:
    """Return a receive channel handing ``body`` over in one go."""
    remaining = iter(({"type": "http.request", "body": body, "more_body": False},))

    async def receive() -> Message:
        return next(remaining, {"type": "http.disconnect"})

    return receive


def asgi_scope(
    method: str = "GET",
    *,
    path: str = "/",
    query: bytes = b"",
    headers: Iterable[tuple[bytes, bytes]] = ((b"host", b"bookshop.test"),),
) -> dict[str, object]:
    """Return the connection a server hands over for one request.

    The matched route's parameters start out empty: a test that needs them
    writes them onto ``scope["path_params"]``, which is where routing puts
    them.

    Args:
        method: The HTTP method.
        path: The whole target path, mount prefix included.
        query: The query string as it was sent.
        headers: The headers as they came off the wire.

    Returns:
        The connection, as the server described it.
    """
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("latin-1"),
        "root_path": "",
        "query_string": query,
        "headers": list(headers),
        "client": ("127.0.0.1", 51234),
        "server": ("bookshop.test", 80),
        "path_params": {},
    }


def asgi_request(
    method: str = "GET",
    *,
    path: str = "/",
    query: bytes = b"",
    headers: Iterable[tuple[bytes, bytes]] = ((b"host", b"bookshop.test"),),
    body: bytes = b"",
) -> Request:
    """Return the request a server handing over this connection would give.

    The matched route's parameters start out empty: a test that needs them
    writes them onto ``request.scope["path_params"]``, which is where routing
    puts them.

    Args:
        method: The HTTP method.
        path: The whole target path, mount prefix included.
        query: The query string as it was sent.
        headers: The headers as they came off the wire.
        body: The payload.

    Returns:
        The framework's own request over that connection.
    """
    return Request(asgi_scope(method, path=path, query=query, headers=headers), received(body))
