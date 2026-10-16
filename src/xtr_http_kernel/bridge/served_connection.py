"""The connection a served request reads its late answers from.

The lifecycle needs a request message before anything has read the body —
a listener may answer at the request, and reading the body to build one
would buffer every request. The message is the bridge factory's to
build, born connected to this: the head read off the connection at
once, the body side answered late, through here. What stays on this
side is the connection's own lifecycle — the materialisation that
reads the wire once and parses what it read, the replay that hands the
application its bytes back after a listener drained the wire, and the
close that shuts the form a read parsed — none of which a message,
framework-free, can know how to do.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast, final

from starlette.datastructures import FormData
from starlette.requests import Request
from typing_extensions import override

# Read at runtime: materialisation prefers the framework's own connection,
# whose caches spare a second reading of the wire, and the refusal when no
# request is being served is what tells this connection to read its own.
from xtr_dependency_injection.exception import FastapiIntegrationError
from xtr_dependency_injection.integration.fastapi import current_connection
from xtr_http_message import RequestSource, ServerRequest

if TYPE_CHECKING:
    from collections.abc import Mapping

    from starlette.types import Message, Receive, Scope
    from xtr_http_message_contracts import ServerRequestInterface

    from .http_message_factory_interface import HttpMessageFactoryInterface

__all__ = [
    "SERVED_REQUEST_SCOPE_KEY",
    "ServedConnection",
    "served_connection_of",
    "served_request_of",
]

SERVED_REQUEST_SCOPE_KEY: Final = "_xtr_http_kernel_served_request"
"""Where the connection of a served request is parked, on the connection's own scope.

The scope is the one object the lifecycle middleware, the framework's own
request and every listener share, and it outlives the response into the
background tasks — which is what makes it the place to find the one
connection of a request again.
"""


def served_connection_of(scope: Scope) -> ServedConnection | None:
    """Return the connection parked on ``scope``, if one is.

    Args:
        scope: The connection as the server described it.

    Returns:
        The one connection the request it describes was served over, or
        ``None`` when nothing served one — no lifecycle middleware, and
        no scoped service asked yet.
    """
    connection = scope.get(SERVED_REQUEST_SCOPE_KEY)
    return connection if isinstance(connection, ServedConnection) else None


def served_request_of(scope: Scope) -> ServerRequestInterface | None:
    """Return the served request parked on ``scope``, if the lifecycle put one there.

    Args:
        scope: The connection as the server described it.

    Returns:
        The one request message of the connection, or ``None`` when no
        lifecycle middleware served it — a bridge-only application,
        where the scoped factory builds the message itself.
    """
    connection = served_connection_of(scope)
    return connection.message if connection is not None else None


@final
class ServedConnection(RequestSource):
    """The connection a served request reads its late answers from.

    Built from the framework's own request object — the scope and the
    channel it arrived on — and the factory that parses a body per its
    content type. The head of the message is read off the connection by
    the factory that builds it; what this side owns is everything that
    arrives late: the body, read once on demand and parsed on the way;
    the parsed body and the uploaded files, answered as far as the read
    has gone; and the route's path parameters, read as they are now.
    """

    __slots__ = (
        "_body",
        "_closed",
        "_files",
        "_message",
        "_message_factory",
        "_parsed",
        "_request",
    )

    def __init__(
        self,
        framework_request: Request,
        message_factory: HttpMessageFactoryInterface,
    ) -> None:
        """Hold ``framework_request``, reading the body through it when asked to.

        The connection parks itself on its request's scope, under this
        package's private key: whichever of the lifecycle middleware and
        the scoped request service builds a connection's message first,
        the other finds the same connection there, so one connection
        serves one request and no path builds a second.

        Args:
            framework_request: The request the framework is serving,
                whose connection this side reads through.
            message_factory: Parses the body per its content type, the
                eager factory's rules — a form for form types, a JSON
                object for JSON, nothing otherwise.
        """
        self._request = framework_request
        self._message_factory = message_factory
        self._message: ServerRequest | None = None
        self._body: bytes | None = None
        self._parsed: object | None = None
        self._files: Mapping[str, object] = {}
        self._closed = False
        framework_request.scope[SERVED_REQUEST_SCOPE_KEY] = self

    @property
    def message(self) -> ServerRequest | None:
        """The one request message served over this connection, once built.

        The factory that builds the message records it here, so the
        connection answers the same instance however many times it is
        asked — one request, one message.
        """
        return self._message

    def park(self, message: ServerRequest) -> ServerRequest:
        """Record ``message`` as the one request this connection serves.

        Args:
            message: The message built over this connection.

        Returns:
            The same message, for the builder to hand on.
        """
        self._message = message
        return message

    @override
    async def materialise(self) -> bytes:
        """Read the whole body once, parsing it per its content type, and answer its bytes.

        The read goes through the framework's own request where one is
        being served, so the body and the form it already read are shared
        rather than read off the wire a second time. A form the framework
        parsed left nothing raw on the wire — a submitted form is the
        body, taken apart — so the bytes answered for one are empty, and
        the form itself lands in the parsed side.

        Returns:
            The raw bytes of the body.
        """
        body = self._body
        if body is None:
            request = self._serving()
            body = await self._raw_body(request)
            parsed = await self._message_factory.create_request(request)
            self._parsed = parsed.get_parsed_body()
            self._files = parsed.get_uploaded_files()
            self._body = body

        return body

    @override
    def parsed_body(self) -> object | None:
        """Return what parsing the body yielded, or ``None`` until it has.

        The parsed side is filled when the body is materialised — a form
        is parsed then, and the fields in it are gathered — so before
        any body read this answers ``None``.
        """
        return self._parsed

    @override
    def uploaded_files(self) -> Mapping[str, object]:
        """Return the files that came with the body, empty until it is read."""
        return self._files

    @override
    def attributes(self) -> Mapping[str, object]:
        """Return what has been derived from the request while handling it.

        Read off the connection each time, so the named parameters the
        matched route fills in are there as soon as routing has filled
        them — which is after the message exists.
        """
        return dict(cast("Mapping[str, object]", self._request.scope.get("path_params", {})))

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
        buffered = self._body
        if buffered is None:
            return receive

        replayed = False

        async def replaying() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": buffered, "more_body": False}
            return await receive()

        return replaying

    async def close(self) -> None:
        """Close the form this connection parsed, if it parsed one, exactly once.

        The lifecycle middleware calls this as the request leaves, and the
        scoped request service as its scope ends — whichever gets there
        first does the closing, and the other finds nothing left to do.
        """
        form = self._parsed
        if self._closed or not isinstance(form, FormData):
            return
        self._closed = True
        await form.close()

    def _serving(self) -> Request:
        """Return the request to read the body through: the framework's own when one is.

        The framework caches the body and the form it read on its own
        request object, so reading through that one shares those caches;
        before routing there is none, and this connection's own request
        reads the wire.
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
