"""HTTP messages, as the request and response the framework serves."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final, final

from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from typing_extensions import override

from xtr_http_kernel.exception import InvalidCookieError

from ._headers import raw_headers
from .starlette_http_factory_interface import StarletteHttpFactoryInterface

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

    from starlette.types import Message, Receive
    from xtr_http_message_contracts import (
        ResponseInterface,
        ServerRequestInterface,
        StreamInterface,
    )

__all__ = ["StarletteHttpFactory"]

_BUFFER_LENGTH: Final = 16372
"""How much of a body goes out at a time while it is being streamed."""

_DEFAULT_PORTS: Final[Mapping[str, int]] = {"http": 80, "https": 443, "ws": 80, "wss": 443}

_DEFAULT_SCHEME: Final = "http"
_SET_COOKIE: Final = "Set-Cookie"
_CONTENT_LENGTH: Final = b"content-length"

_COOKIE_NAME: Final = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")
"""A cookie name: the same token a header name is, and never empty."""

_VISIBLE: Final = r"[\x21-\x3a\x3c-\x7e]"
"""One visible ASCII character, apart from the one cookies are parted by."""

_COOKIE_VALUE: Final = re.compile(rf"(?:{_VISIBLE}(?:[\x20-\x3a\x3c-\x7e]*{_VISIBLE})?)?")
"""A cookie value the framework reads back exactly as it was written.

Visible ASCII characters, spaces allowed between them but not at either end
— the reader strips those — and no ``;``, which the reader splits on. Wider
than the cookie grammar by the space, the comma, the double quote and the
backslash, because the framework's own reader hands those back from a header
a browser can send: a value the server quoted arrives unquoted, so a cookie
that came off a real request can hold them and has to be sendable again.
"""


def _is_quoted(value: str) -> bool:
    """Tell whether a value is wrapped in the double quotes the reader takes off."""
    return len(value) > 1 and value.startswith('"') and value.endswith('"')


def _as_sent(name: str, value: str) -> str:
    """Return one cookie as the header carries it, refusing what would not read back.

    Raises:
        InvalidCookieError: When the name or the value is one the header
            cannot carry unchanged.
    """
    if _COOKIE_NAME.fullmatch(name) is None:
        raise InvalidCookieError(
            name,
            "a cookie name is one or more of the characters a header name may hold —"
            " letters, digits and !#$%&'*+-.^_`|~ — and this is not",
        )

    if ";" in value:
        raise InvalidCookieError(
            name,
            'its value holds ";", which is what one cookie is parted from the next by,'
            " so the value would be read back as cookies of its own",
        )

    if _COOKIE_VALUE.fullmatch(value) is None:
        raise InvalidCookieError(
            name,
            "a cookie value is visible ASCII characters, with a space allowed between"
            " them but not at either end, and this is not",
        )

    if _is_quoted(value):
        raise InvalidCookieError(
            name,
            "its value is wrapped in double quotes, which a reader takes off, so the"
            " value would be read back without them",
        )

    return f"{name}={value}"


def _cookie_header(cookies: Mapping[str, str]) -> tuple[bytes, bytes]:
    """Return the ``Cookie`` header the cookies of a request message amount to.

    Raises:
        InvalidCookieError: When one of the cookies would not be read back as
            it was.
    """
    sent = "; ".join(_as_sent(name, value) for name, value in cookies.items())

    return (b"cookie", sent.encode("latin-1"))


def _receive_whole(payload: bytes) -> Receive:
    """Return a receive channel handing ``payload`` over in one go."""
    body: Message = {"type": "http.request", "body": payload, "more_body": False}
    remaining = iter((body,))

    async def receive() -> Message:
        return next(remaining, {"type": "http.disconnect"})

    return receive


def _receive_chunks(body: StreamInterface, length: int) -> Receive:
    """Return a receive channel reading ``body`` a chunk at a time, as it is asked for."""
    if body.is_seekable():
        body.rewind()

    async def receive() -> Message:
        chunk = body.read(length) if body.is_readable() else b""

        return {"type": "http.request", "body": chunk, "more_body": chunk != b""}

    return receive


async def _chunks(body: StreamInterface, length: int) -> AsyncIterator[bytes]:
    """Yield ``body`` a chunk at a time, from its first byte to its last."""
    if body.is_seekable():
        body.rewind()

    if not body.is_readable():
        # Nothing to read from, which the stream itself answers for safely.
        yield bytes(body)
        return

    # The end is the read that comes back with nothing, and only that: a pipe,
    # a socket or any unbuffered source answers a read with what has arrived
    # so far, which is routinely less than was asked for.
    while True:
        chunk = body.read(length)
        if chunk == b"":
            break
        yield chunk


@final
class StarletteHttpFactory(StarletteHttpFactoryInterface):
    """Builds the framework's own request and response out of HTTP messages.

    ```python
    sendable = factory.create_response(message)
    ```

    A request's components are the connection the framework reads them off:
    the URI becomes the scheme, the path, the query string and the address,
    the environment parameters stand underneath as the server's own entries,
    and the body becomes the channel the framework reads it from — whole, or
    a chunk at a time where that is asked for.

    Three parts of a request message have no slot of their own on the
    framework's request, which builds them out of the wire itself: the query
    parameters come from the query string, and the parsed body and the
    uploaded files from the body. A message whose parameters were replaced
    apart from its URI, or whose form was replaced apart from its body,
    therefore arrives carrying what its URI and its body say.
    """

    __slots__ = ("_buffer_length",)

    def __init__(self, buffer_length: int = _BUFFER_LENGTH) -> None:
        """Stream bodies ``buffer_length`` bytes at a time.

        Args:
            buffer_length: How much of a body is handed over at a time while
                it is being streamed, in bytes.
        """
        self._buffer_length = buffer_length

    @override
    def create_request(
        self,
        server_request: ServerRequestInterface,
        streamed: bool = False,
    ) -> Request:
        """Return ``server_request`` as a request the framework can serve.

        The environment parameters stand underneath the connection, each
        under the name the message holds it by, and what the URI, the method,
        the protocol version and the headers say is laid over them — so a
        message that came from a served request arrives back carrying the
        connection it came from, corrected by whatever was changed since.

        The cookies become a ``Cookie`` header where the message carries
        none, since that header is where the framework reads cookies from; a
        message that carries one keeps it as it is. A cookie the header
        cannot carry unchanged is refused rather than written out: the
        cookies of a message are a plain mapping nothing checked on the way
        in, and a value holding ``;`` would come back as further cookies.

        Args:
            server_request: The request message.
            streamed: Whether the body is handed over a chunk at a time as
                the framework asks for it rather than read whole up front.

        Returns:
            The same request, as the framework's own.

        Raises:
            InvalidCookieError: When the message carries a cookie a ``Cookie``
                header cannot carry unchanged, and no such header of its own.
        """
        uri = server_request.get_uri()
        scheme = uri.get_scheme() or _DEFAULT_SCHEME
        path = uri.get_path()
        host = uri.get_host()
        port = uri.get_port()

        headers = raw_headers(server_request)
        cookies = server_request.get_cookie_params()
        if len(cookies) > 0 and not server_request.has_header("cookie"):
            headers.append(_cookie_header(cookies))

        body = server_request.get_body()
        scope = {
            **server_request.get_server_params(),
            "type": "http",
            "http_version": server_request.get_protocol_version(),
            "method": server_request.get_method(),
            "scheme": scheme,
            "path": path,
            "raw_path": path.encode("latin-1"),
            "query_string": uri.get_query().encode("latin-1"),
            "headers": headers,
            "server": None
            if host == ""
            else (host, port if port is not None else _DEFAULT_PORTS.get(scheme, 80)),
            "path_params": dict(server_request.get_attributes()),
        }

        return Request(
            scope,
            _receive_chunks(body, self._buffer_length) if streamed else _receive_whole(bytes(body)),
        )

    @override
    def create_response(
        self,
        response: ResponseInterface,
        streamed: bool = False,
    ) -> Response:
        """Return ``response`` as a response the framework can send.

        ``Set-Cookie`` is taken off and put back one value per header, since a
        cookie is never joined with another. The length of the body is
        declared where the message does not declare one itself and the body
        is not being streamed.

        The protocol version is left behind: the framework's response carries
        none, the server writing the one the connection actually spoke.

        Args:
            response: The response message.
            streamed: Whether the body goes out a chunk at a time rather than
                whole.

        Returns:
            The same response, as the framework's own.
        """
        set_cookie = response.get_header(_SET_COOKIE)
        without_cookies = response.without_header(_SET_COOKIE)
        body = without_cookies.get_body()
        status = response.get_status_code()

        built: Response = (
            StreamingResponse(_chunks(body, self._buffer_length), status_code=status)
            if streamed
            else Response(bytes(body), status_code=status)
        )

        headers = raw_headers(without_cookies)
        headers.extend((b"set-cookie", value.encode("latin-1")) for value in set_cookie)
        if not any(name == _CONTENT_LENGTH for name, _ in headers):
            # What the response worked out for the body it was built with,
            # which is nothing at all while the body is being streamed.
            headers.extend(pair for pair in built.raw_headers if pair[0] == _CONTENT_LENGTH)
        # Replaced in place: the response may already have handed this very
        # list to a view of its headers.
        built.raw_headers[:] = headers

        return built
