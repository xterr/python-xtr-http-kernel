"""A response that is an HTTP message and what the framework sends, at once."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Final, Self, cast, final

from starlette.datastructures import MutableHeaders
from starlette.responses import Response as StarletteResponse
from typing_extensions import override
from xtr_http_message import Response as ResponseMessage
from xtr_http_message import Stream
from xtr_http_message_contracts import ResponseInterface

from ._headers import raw_headers, with_raw_headers

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from starlette.background import BackgroundTask
    from starlette.types import Receive, Scope, Send
    from xtr_http_message_contracts import StreamInterface

__all__ = ["Response"]

_PROTOCOL: Final = "1.1"
_CHUNK_LENGTH: Final = 16372
"""How much of a body of unknown length goes out at a time."""

_CONTENT_LENGTH: Final = b"content-length"
_FIRST_FINAL_STATUS: Final = 200
"""Below this a response is interim: the answer itself is still to come."""

_BODYLESS_STATUSES: Final = frozenset({204, 304})
"""The final statuses whose answer is the status itself: no content, unchanged."""


@final
class Response(StarletteResponse, ResponseInterface):
    """A response an endpoint fills in as a message and returns as it is.

    Two things at once, deliberately: every member of the response contract
    is here, so a library that knows only the contract can write a status, a
    header or a body into it; and it is the framework's own response class,
    so an endpoint returns it without anything converting it.

    ```python
    @app.post("/books")
    async def add(response: Injected[Response]) -> Response:
        _ = response.get_body().write(b'{"id": 7}')
        return response.with_status(201).with_header("content-type", "application/json")
    ```

    An endpoint asks for this class and says it returns it, so the parameter
    and the return annotation are the same type and nothing narrows one to
    the other. A library asks for ``ResponseInterface`` and is handed this
    very response: the two lead to the same build.

    What goes out is read at the moment of sending, not at the moment of
    building: a body written to after the response was made is sent, and so
    is a header added to it. The length of the body is declared when the
    stream can say how long it is, and otherwise the body goes out a chunk at
    a time with no length at all.

    The framework reads four things off a response it is handed —
    ``status_code``, ``headers`` and ``raw_headers``, ``body``, and
    ``background``. The first three are views of the message rather than
    copies of it, so none of them can fall out of step with what will be
    sent: reading one reads the message, writing one writes the message back.
    The list of wire headers handed out is the view for as long as this
    response lives — reading the message folds in whatever was written
    through it and leaves it holding what the message now says — so a
    ``MutableHeaders`` built on it keeps working however the two sides are
    interleaved.
    ``background`` is the framework's own and is kept as it sets it. A
    response made from this one by a ``with_*`` method is another of these,
    carrying the same background task.
    """

    __slots__ = ("_message", "_view")

    def __init__(  # pyright: ignore[reportMissingSuperCall] — see below.
        self,
        status: int = 200,
        reason: str | None = None,
    ) -> None:
        """Build a response carrying ``status``, with no header and no body yet.

        Headers and a body are written afterwards — ``with_header`` and
        ``get_body().write(...)`` — which is what an endpoint handed one of
        these does. To send a message built somewhere else, convert it with
        :class:`~xtr_http_kernel.bridge.StarletteHttpFactory` instead.

        The framework's own constructor is deliberately not called: it renders
        a body, assigns a status and works out headers, and all three of those
        are views of the message here, which is the state this response has.

        Args:
            status: The status code.
            reason: The reason phrase. ``None`` — the default — takes the one
                recommended for ``status``; an empty string leaves the
                response with none.
        """
        self._message: ResponseInterface = ResponseMessage(status, None, None, _PROTOCOL, reason)
        self._view: list[tuple[bytes, bytes]] | None = None
        self.background: BackgroundTask | None = None

    # ─── the message ────────────────────────────────────────────────────

    @override
    def get_status_code(self) -> int:
        """Return the status code of the response.

        Returns:
            The three-digit code saying how the server got on with the
            request.
        """
        return self._settled().get_status_code()

    @override
    def get_reason_phrase(self) -> str:
        """Return the reason phrase that goes with the status code.

        Returns:
            The reason phrase, or an empty string when the response carries
            none.
        """
        return self._settled().get_reason_phrase()

    @override
    def with_status(self, code: int, reason_phrase: str = "") -> Self:
        """Return an instance carrying ``code`` and, optionally, ``reason_phrase``.

        Args:
            code: The status code to set.
            reason_phrase: The phrase to go with ``code``. Left out or empty,
                the one recommended for ``code`` is filled in where there is
                one.

        Returns:
            A new instance; this one is left as it was.

        Raises:
            ValueError: When the code is not a status code.
        """
        return self._around(self._settled().with_status(code, reason_phrase))

    @override
    def get_protocol_version(self) -> str:
        """Return the HTTP version of the message.

        Returns:
            The version number alone, such as ``"1.1"``.
        """
        return self._settled().get_protocol_version()

    @override
    def with_protocol_version(self, version: str) -> Self:
        """Return an instance carrying ``version``.

        The version is the message's own; what a connection actually spoke is
        the server's to say, so changing this does not change what goes out.

        Args:
            version: The HTTP version number alone, such as ``"1.1"``.

        Returns:
            A new instance; this one is left as it was.
        """
        return self._around(self._settled().with_protocol_version(version))

    @override
    def get_headers(self) -> Mapping[str, Sequence[str]]:
        """Return every header, each name mapped to all of its values.

        Returns:
            Each header name as it will go over the wire, mapped to the
            values recorded under it.
        """
        return self._settled().get_headers()

    @override
    def has_header(self, name: str) -> bool:
        """Tell whether a header is present, matching ``name`` without case.

        Args:
            name: The header name, in any case.

        Returns:
            ``True`` when some header name matches ``name`` ignoring case.
        """
        return self._settled().has_header(name)

    @override
    def get_header(self, name: str) -> Sequence[str]:
        """Return every value recorded under a header, matched without case.

        Args:
            name: The header name, in any case.

        Returns:
            The values under that header, in order; empty for a header the
            response does not carry.
        """
        return self._settled().get_header(name)

    @override
    def get_header_line(self, name: str) -> str:
        """Return the values of a header joined with commas, matched without case.

        Args:
            name: The header name, in any case.

        Returns:
            The values joined with ``", "``; an empty string for a header the
            response does not carry.
        """
        return self._settled().get_header_line(name)

    @override
    def with_header(self, name: str, value: str | Sequence[str]) -> Self:
        """Return an instance whose ``name`` header holds ``value`` and nothing else.

        Args:
            name: The header name, in any case.
            value: One value, or every value the header is to hold.

        Returns:
            A new instance; this one is left as it was.

        Raises:
            ValueError: When the name or a value is not one.
        """
        return self._around(self._settled().with_header(name, value))

    @override
    def with_added_header(self, name: str, value: str | Sequence[str]) -> Self:
        """Return an instance with ``value`` appended to the ``name`` header.

        Args:
            name: The header name, in any case.
            value: One value, or every value to append.

        Returns:
            A new instance; this one is left as it was.

        Raises:
            ValueError: When the name or a value is not one.
        """
        return self._around(self._settled().with_added_header(name, value))

    @override
    def without_header(self, name: str) -> Self:
        """Return an instance with the ``name`` header gone.

        Args:
            name: The header name, in any case.

        Returns:
            A new instance; this one is left as it was.
        """
        return self._around(self._settled().without_header(name))

    @override
    def get_body(self) -> StreamInterface:
        """Return the body of the response, to read or to write to.

        Writing to it after the response was built is the point: what is
        written is what goes out, because the body is read when the response
        is sent.

        Returns:
            The body, as a stream.
        """
        return self._settled().get_body()

    @override
    def with_body(self, body: StreamInterface) -> Self:
        """Return an instance carrying ``body``.

        Args:
            body: The stream the new instance reads its body from.

        Returns:
            A new instance, or this one when it already reads that very
            stream.
        """
        return self._around(self._settled().with_body(body))

    # ─── what the framework reads ───────────────────────────────────────

    @property
    def status_code(self) -> int:
        """The status code, as the message holds it."""
        return self._settled().get_status_code()

    @status_code.setter
    def status_code(self, code: int) -> None:  # pyright: ignore[reportIncompatibleUnannotatedOverride] — a view of the message's status, not a field of its own; see the class docstring.
        """Set the status code on the message, taking the phrase that goes with it."""
        self._message = self._settled().with_status(code)

    @property
    def raw_headers(self) -> list[tuple[bytes, bytes]]:
        """The headers as the wire wants them, written back to the message when changed."""
        view = self._view
        if view is None:
            view = raw_headers(self._message)
            self._view = view

        return view

    @raw_headers.setter
    def raw_headers(self, raw: list[tuple[bytes, bytes]]) -> None:  # pyright: ignore[reportIncompatibleUnannotatedOverride] — a view of the message's headers, not a field of its own; see the class docstring.
        """Make ``raw`` the headers of the message, dropping whatever it held."""
        self._message = with_raw_headers(self._message, raw)
        self._refill()

    @property
    def headers(self) -> MutableHeaders:
        """The headers as a mapping the framework can read and change."""
        return MutableHeaders(raw=self.raw_headers)

    @property
    def body(self) -> bytes:
        """Everything in the body, read from the first byte to the last."""
        return bytes(self._settled().get_body())

    @body.setter
    def body(self, payload: bytes) -> None:  # pyright: ignore[reportIncompatibleUnannotatedOverride] — a view of the message's body, not a field of its own; see the class docstring.
        """Make ``payload`` the whole body, replacing the stream it had."""
        self._message = self._settled().with_body(Stream.create(payload))

    @override
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Send the response as it stands now, then run the background task.

        Args:
            scope: The connection being answered.
            receive: Unused: a response reads nothing.
            send: Where the response goes.
        """
        del receive
        if cast("str", scope["type"]) == "websocket":
            send = self._wrap_websocket_denial_send(send)

        message = self._settled()
        status = message.get_status_code()
        body = message.get_body()
        headers = raw_headers(message)
        length = body.get_size()
        if length is not None and _may_declare_length(status, headers):
            headers.append((_CONTENT_LENGTH, str(length).encode("latin-1")))

        await send({"type": "http.response.start", "status": status, "headers": headers})
        await self._send_body(body, send)

        if self.background is not None:
            await self.background()

    async def _send_body(self, body: StreamInterface, send: Send) -> None:
        """Send the body, a chunk at a time, ending with the chunk that says so."""
        if body.is_seekable():
            body.rewind()

        if not body.is_readable():
            # Nothing to read from, which the stream itself answers for safely.
            await send({"type": "http.response.body", "body": bytes(body)})
            return

        # The end is the read that comes back with nothing, and only that: a
        # pipe, a socket or any unbuffered source answers a read with what has
        # arrived so far, which is routinely less than was asked for.
        while True:
            chunk = body.read(_CHUNK_LENGTH)
            if chunk == b"":
                break
            await send({"type": "http.response.body", "body": chunk, "more_body": True})

        await send({"type": "http.response.body", "body": b""})

    def _settled(self) -> ResponseInterface:
        """Return the message, with whatever was written through the wire view folded in.

        The view the framework reads and changes is a list of byte pairs, as
        the wire wants them; the message is where they belong. Handing the
        view out and folding it back in here is what keeps one from drifting
        from the other, whichever side was written to. The list stays the
        view: dropping it would quietly cut off a caller still holding it,
        so it is refilled from the message instead.
        """
        view = self._view
        if view is None:
            return self._message

        if view != raw_headers(self._message):
            self._message = with_raw_headers(self._message, view)
            self._refill()

        return self._message

    def _refill(self) -> None:
        """Leave the wire view, where one was handed out, holding the message's headers."""
        view = self._view
        if view is not None:
            view[:] = raw_headers(self._message)

    def _around(self, message: ResponseInterface) -> Self:
        """Return this response's twin around ``message``, background task and all."""
        if message is self._message:
            return self

        twin = copy.copy(self)
        twin._message = message  # noqa: SLF001 — a copy of this very class.
        twin._view = None  # noqa: SLF001 — a copy of this very class.

        return twin


def _may_declare_length(status: int, headers: list[tuple[bytes, bytes]]) -> bool:
    """Tell whether the length of the body is this response's to declare.

    A response the message already declares a length for keeps the one it
    declares, and a status whose answer is the status itself — interim,
    nothing to send, nothing changed — declares none at all.
    """
    return (
        status >= _FIRST_FINAL_STATUS
        and status not in _BODYLESS_STATUSES
        and not any(name == _CONTENT_LENGTH for name, _ in headers)
    )
