"""What a served request answers as it is read: its body, its form, its files.

The body is one lazy stream — nothing is read until something reads it — and
the first read materialises the whole body once, parsing it per its content
type on the way. This is also where the lifecycle's seams live: the replay
that hands the application its bytes back after a listener drained the wire,
and the close that shuts the form the read parsed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Protocol, cast, runtime_checkable

from starlette.datastructures import FormData
from starlette.requests import Request

# Read at runtime: materialisation prefers the framework's own connection,
# whose caches spare a second reading of the wire, and the refusal when no
# request is being served is what tells this message to read its own.
from xtr_dependency_injection.exception import FastapiIntegrationError
from xtr_dependency_injection.integration.fastapi import current_connection

from ._media_types import has_parsed_side
from ._served_body import ServedBody
from ._served_head import ServedHead

if TYPE_CHECKING:
    from collections.abc import Mapping

    from starlette.types import Message, Receive
    from xtr_http_message_contracts import ServerRequestInterface, StreamInterface
    from xtr_http_message_contracts.factory import (
        StreamFactoryInterface,
        UriFactoryInterface,
    )

__all__ = ["ServedReading"]


@runtime_checkable
class BodyParser(Protocol):
    """What a materialisation reads a body through: the eager factory's parsing rules.

    The bridge's own message factory is the one implementation; a protocol
    rather than its interface so the served request does not import the
    module that imports it.
    """

    async def create_request(self, request: Request) -> ServerRequestInterface:
        """Return ``request`` as a server request message, body and form read."""
        ...


class ServedReading(ServedHead):
    """The read side of a served request: its body, and everything parsed from it.

    A mixin, as the head before it: this is the part of a served request that
    costs input, and the class composing it —
    :class:`~xtr_http_kernel.bridge.served_request.ServedRequest` — carries
    the rest.
    """

    __slots__: ClassVar[tuple[str, ...]] = (
        "_body",
        "_closed",
        "_files",
        "_messages",
        "_parsed",
        "_streams",
    )

    def __init__(
        self,
        request: Request,
        uris: UriFactoryInterface,
        streams: StreamFactoryInterface,
        messages: BodyParser,
    ) -> None:
        """Hold ``request``, building its body as one lazy stream over the wire.

        Args:
            request: The request the framework is serving.
            uris: Builds the URI of the request, so the implementation stays
                the application's choice.
            streams: Builds the buffer the body is materialised into.
            messages: Parses the body per its content type, the eager
                factory's rules — a form for form types, a JSON object for
                JSON, nothing otherwise.
        """
        super().__init__(request, uris)
        self._streams: StreamFactoryInterface = streams
        self._messages: BodyParser = messages
        self._body: ServedBody | None = None
        self._parsed: object | None = None
        self._files: Mapping[str, object] = {}
        self._closed: bool = False

    @property
    def materialised(self) -> bool:
        """Tell whether the body has been read into memory.

        The lifecycle middleware asks this after its request listeners have
        run: a listener that read the body drained the wire, so the
        application is handed a receive that replays the buffered bytes
        instead of the empty channel the drain left.
        """
        return self._body is not None and self._body.materialised

    async def ensure_parsed(self) -> None:
        """Materialise a body that has a parsed side, so the contract's answers hold.

        The scoped request service calls this before the message is handed to
        anything: a consumer written against the contract reads
        :meth:`get_parsed_body` without reading the stream first, and only a
        body that has been read can answer it — so a form or a JSON body is
        read here, at the one seam that can still await. A body with no parsed
        side is left to whoever reads it: an upload, a stream and a request
        with no body at all cost nothing until asked. Idempotent.
        """
        if self.materialised or not has_parsed_side(self._request.headers.get("content-type", "")):
            return
        _ = await self.get_body().get_contents()

    async def replay(self, receive: Receive) -> Receive:
        """Return the receive the application is to be handed for this request.

        With the body materialised, the application is handed a channel that
        yields the buffered bytes as one request message and then hands
        back whatever the original channel still offers — the disconnect,
        when it comes. With nothing materialised, the original channel
        passes through untouched: no request is wrapped unless a listener
        read its body.

        Args:
            receive: The channel the connection arrived on.

        Returns:
            The channel to hand the application.
        """
        body = self._body
        if body is None or not body.materialised:
            return receive

        buffered = await body.contents()
        replayed = False

        async def replaying() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": buffered, "more_body": False}
            return await receive()

        return replaying

    async def close(self) -> None:
        """Close the form this request parsed, if it parsed one, exactly once.

        The lifecycle middleware calls this as the request leaves, and the
        scoped request service as its scope ends — whichever gets there
        first does the closing, and the other finds nothing left to do.
        """
        form = self._parsed
        if self._closed or not isinstance(form, FormData):
            return
        self._closed = True
        await form.close()

    def get_body(self) -> StreamInterface:
        """Return the body, as the one lazy stream this request hands out.

        Nothing is read until something reads the stream; the first read
        materialises the whole body, and every later one is served out of
        the buffer.
        """
        if self._body is None:
            self._body = ServedBody(self._materialise)
        return self._body

    def get_uploaded_files(self) -> Mapping[str, object]:
        """Return the files that came with the request.

        The files are gathered when the body is materialised — a form is
        parsed then, and the files in it are wrapped where they lie — so
        before any body read this answers an empty mapping; the scoped
        request service reads a form before it hands the message on.
        """
        return self._files

    def get_parsed_body(self) -> object | None:
        """Return the parameters found in the body of the request.

        A body nobody has read has yielded nothing, so this answers ``None``
        until the body is materialised and parsed. A body that has a parsed
        side — a form, JSON — is materialised before the container hands this
        message to a service or an endpoint, so a consumer written against the
        contract never meets the ``None``; it is the lifecycle's own events
        that carry the message unread — a listener reads the stream, and the
        reading parses.
        """
        return self._parsed

    def get_attributes(self) -> Mapping[str, object]:
        """Return what was derived from the request while handling it.

        Read off the connection each time, so the named parameters the
        matched route fills in are there as soon as routing has filled
        them — which is after this message exists.
        """
        return dict(cast("Mapping[str, object]", self._request.scope.get("path_params", {})))

    def get_attribute(self, name: str, default: object | None = None) -> object | None:
        """Return one of the attributes :meth:`get_attributes` describes."""
        params = cast("Mapping[str, object]", self._request.scope.get("path_params", {}))
        return params.get(name, default)

    async def _materialise(self) -> StreamInterface:
        """Read the whole body once, parsing it per its content type, and buffer it.

        The read goes through the framework's own request where one is being
        served, so the body and the form it already read are shared rather
        than read off the wire a second time. A form the framework parsed
        left nothing raw on the wire — a submitted form is the body, taken
        apart — so the buffer holds the empty stream where that happened,
        and the form itself as the parsed body.
        """
        request = self._serving()
        body = await self._raw_body(request)
        parsed = await self._messages.create_request(request)
        self._parsed = parsed.get_parsed_body()
        self._files = parsed.get_uploaded_files()
        return self._streams.create_stream(body)

    def _serving(self) -> Request:
        """Return the request to read the body through: the framework's own when one is.

        The framework caches the body and the form it read on its own
        request object, so reading through that one shares those caches;
        before routing there is none, and this message's own request reads
        the wire.
        """
        try:
            connection = current_connection()
        except FastapiIntegrationError:
            return self._request
        return connection if isinstance(connection, Request) else self._request

    async def _raw_body(self, request: Request) -> bytes:
        """Return the raw body of ``request``, empty where a form already took the wire.

        Raises:
            RuntimeError: Propagated from the read, unless it is the one the
                framework raises for a wire its form already consumed.
        """
        try:
            return await request.body()
        except RuntimeError:
            # The framework parsed a form off this wire: the raw bytes are
            # gone, and the form is the parsed body instead.
            return b""
