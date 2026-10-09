"""The URI of a served request, read off the connection's own components.

Assembled component by component — scheme, host, port, path, query string —
rather than by writing a URI out and reading it back: the server has already
taken the request line apart, and putting it together only to split it again
is where a host with a port in it, or a path with a per cent sign in it, goes
wrong.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast

if TYPE_CHECKING:
    from collections.abc import Iterable

    from starlette.types import Scope
    from xtr_http_message_contracts import UriInterface
    from xtr_http_message_contracts.factory import UriFactoryInterface

__all__ = ["scope_uri"]

_MAX_PORT: Final = 0xFFFF
"""The highest port a connection can name; a greater one names no server."""

_DEFAULT_SCHEME: Final = "http"

_NO_AUTHORITY: Final[tuple[str, int | None]] = ("", None)
"""What an unreadable or absent authority reads as: no host, no port."""


def scope_uri(uris: UriFactoryInterface, scope: Scope) -> UriInterface:
    """Return the URI the connection in ``scope`` is for.

    Args:
        uris: The factory the URI is built by, so the implementation stays the
            application's choice.
        scope: The connection as the server describes it.

    Returns:
        The URI: the scheme and authority the connection arrived on, the whole
        target path — the mount prefix included, since that is what the server
        reports — and the query string as it was sent. A connection naming no
        address and sending no ``Host`` header — which no server and no
        HTTP/1.1 client does — leaves the URI with no authority at all.
    """
    host, port = _authority(scope)
    query = cast("bytes", scope.get("query_string", b"")).decode("latin-1")

    return (
        uris.create_uri()
        .with_scheme(cast("str", scope.get("scheme", _DEFAULT_SCHEME)))
        .with_host(host)
        .with_port(port)
        .with_path(cast("str", scope["path"]))
        .with_query(query)
    )


def _authority(scope: Scope) -> tuple[str, int | None]:
    """Return the host and port the connection names, the client's claim first.

    The ``Host`` header is what the client asked for and so what a URI of the
    request must repeat; the address the server is listening on stands in only
    where that header is missing or unreadable.
    """
    host, port = _host_header(scope)
    if host != "":
        return host, port

    server = cast("tuple[str, int | None] | None", scope.get("server"))
    if server is None:
        return _NO_AUTHORITY

    name, number = server
    # An address with colons in it is one of the long kind, which only reads
    # as a host inside brackets.
    bracketed = f"[{name}]" if ":" in name and not name.startswith("[") else name

    return bracketed, number


def _host_header(scope: Scope) -> tuple[str, int | None]:
    """Return the host and port the ``Host`` header names, if it names any."""
    for name, value in cast("Iterable[tuple[bytes, bytes]]", scope.get("headers", ())):
        if name == b"host":
            return _split_host(value.decode("latin-1"))

    return _NO_AUTHORITY


def _split_host(header: str) -> tuple[str, int | None]:
    """Return the host and port a ``Host`` header holds, or no host at all.

    A header naming something that is not a host and a port — an address of
    the long kind written without its brackets, a port that is not a number,
    a port no connection can have — reads as no host, so that the address the
    server is listening on stands in rather than a nonsense authority
    reaching the request.
    """
    host, separator, port = header.rpartition(":")
    if separator == "" or header.endswith("]"):
        # Either no port at all, or a bracketed address whose colons are the
        # address's own.
        return header, None

    if ":" in host and not host.startswith("["):
        return _NO_AUTHORITY

    if not port.isdigit():
        return _NO_AUTHORITY

    number = int(port)

    return (host, number) if number <= _MAX_PORT else _NO_AUTHORITY
