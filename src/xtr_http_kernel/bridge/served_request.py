"""The request being served, as a read-through view over the connection serving it.

The lifecycle needs a request message before anything has read the body —
a listener may answer at the request, and reading the body to build one
would buffer every request. This is the message that costs nothing to
build: its head is read straight off the connection, its body is a lazy
stream that materialises once on first read, and its attributes follow the
route's path parameters as they are filled in. One instance is parked on
the connection's scope, so the events, the scoped ``server_request``
service and a route's injected message are all the same object.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Self, cast, final

from typing_extensions import override
from xtr_http_message import ServerRequest
from xtr_http_message_contracts import ServerRequestInterface

from ._served_reading import BodyParser, ServedReading

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from starlette.requests import Request
    from starlette.types import Scope
    from xtr_http_message_contracts import StreamInterface, UriInterface
    from xtr_http_message_contracts.factory import (
        StreamFactoryInterface,
        UriFactoryInterface,
    )

__all__ = ["SERVED_REQUEST_SCOPE_KEY", "ServedRequest", "served_request_of"]

SERVED_REQUEST_SCOPE_KEY: Final = "_xtr_http_kernel_served_request"
"""Where the served request of a connection is parked, on the connection's own scope.

The scope is the one object the lifecycle middleware, the framework's own
request and every listener share, and it outlives the response into the
background tasks — which is what makes it the place to find the one served
request of the connection again.
"""


def served_request_of(scope: Scope) -> ServedRequest | None:
    """Return the served request parked on ``scope``, if the lifecycle put one there.

    Args:
        scope: The connection as the server described it.

    Returns:
        The one served request of the connection, or ``None`` when no
        lifecycle middleware served it — a bridge-only application, where
        the scoped factory builds the message itself.
    """
    served = scope.get(SERVED_REQUEST_SCOPE_KEY)
    return served if isinstance(served, ServedRequest) else None


@final
class ServedRequest(ServedReading, ServerRequestInterface):
    """A request message read through the connection that is serving it.

    The head — method, URI, headers, cookies, query parameters,
    environment parameters, protocol version — is read off the connection
    as asked for, and costs no input: nothing crosses the wire. The body is
    one lazy stream: the first read of it materialises the whole body once,
    parsing it per its content type on the way, and every later read is
    served out of the buffer, seekable and rewindable. The parsed body and
    uploaded files answer what that materialisation yielded — ``None`` and
    an empty mapping before it — which is the one recorded deviation from
    the contract's unconditional wording, and one the seam that can still
    await closes where it matters: the scoped request service materialises a
    body that has a parsed side before the container hands this message to
    anything, so only the lifecycle's events carry it unread. A body nobody
    has read cannot be parsed without reading it.

    The attributes are the route's path parameters as they are now, read
    off the scope each time: routing fills them after this message exists,
    and the contract says attributes may change over the course of a
    request.

    The ``with_*`` members return plain copies — immutable snapshots of
    this message as it stands, built by the message implementation — so a
    change a listener makes never reaches the connection or the request
    being served. A copy is not this live view: it answers what was there
    when it was made, and it has no body of its own to read off the wire.
    """

    __slots__ = ()

    def __init__(
        self,
        request: Request,
        uris: UriFactoryInterface,
        streams: StreamFactoryInterface,
        messages: BodyParser,
    ) -> None:
        """Read ``request`` through, building the head from its connection alone.

        The message parks itself on its connection's scope, under this
        package's private key: whichever of the lifecycle middleware and the
        scoped request service builds a connection's message first, the
        other finds the same instance there, so one connection has one
        served request and no path builds a second.

        Args:
            request: The request the framework is serving, whose connection
                this message reads through.
            uris: Builds the URI of the request, so the implementation stays
                the application's choice.
            streams: Builds the buffer the body is materialised into.
            messages: Parses the body per its content type, the eager
                factory's rules — a form for form types, a JSON object for
                JSON, nothing otherwise.
        """
        super().__init__(request, uris, streams, messages)
        request.scope[SERVED_REQUEST_SCOPE_KEY] = self

    def _plain(self) -> ServerRequest:
        """Return this request as it stands, as a plain immutable message.

        Everything the copy carries is read as it is now — the head off the
        connection, the parsed body and the uploaded files as the last
        materialisation left them — so the copy is a snapshot, not a view:
        it is what the ``with_*`` members hand out, per the contract.
        """
        message = ServerRequest(
            self.get_method(),
            self.get_uri(),
            None,
            self.get_body(),
            self.get_protocol_version(),
            self.get_server_params(),
        )
        for name, values in self.get_headers().items():
            try:
                message = message.with_header(name, values)
            except ValueError:
                # A header the message grammar refuses is left out rather
                # than failing the request: the framework let it through.
                continue

        message = (
            message.with_cookie_params(self.get_cookie_params())
            .with_query_params(self.get_query_params())
            .with_uploaded_files(self.get_uploaded_files())
            .with_parsed_body(self.get_parsed_body())
        )
        for name, value in self.get_attributes().items():
            message = message.with_attribute(name, value)

        return message

    def _copy(self, plain: ServerRequest) -> Self:
        """Return ``plain`` as this request's answer to a ``with_*`` call.

        The contract has a ``with_*`` member return a new instance, and the
        instance that answers for this live view is the plain copy: an
        immutable message, not a view over the connection. The ``Self``
        return is what a caller of the contract sees; the object is a plain
        message, and reading it never reaches the connection.
        """
        return cast("Self", cast("object", plain))

    # ─── the message ───────────────────────────────────────────────────

    @override
    def with_protocol_version(self, version: str) -> Self:
        """Return a plain copy carrying ``version``; this view is left as it was."""
        return self._copy(self._plain().with_protocol_version(version))

    @override
    def with_header(self, name: str, value: str | Sequence[str]) -> Self:
        """Return a plain copy carrying ``value`` under ``name`` and nothing else."""
        return self._copy(self._plain().with_header(name, value))

    @override
    def with_added_header(self, name: str, value: str | Sequence[str]) -> Self:
        """Return a plain copy with ``value`` appended to the ``name`` header."""
        return self._copy(self._plain().with_added_header(name, value))

    @override
    def without_header(self, name: str) -> Self:
        """Return a plain copy with the ``name`` header gone."""
        return self._copy(self._plain().without_header(name))

    @override
    def with_body(self, body: StreamInterface) -> Self:
        """Return a plain copy reading its body from ``body``."""
        return self._copy(self._plain().with_body(body))

    # ─── the request ───────────────────────────────────────────────────

    @override
    def with_method(self, method: str) -> Self:
        """Return a plain copy carrying ``method``."""
        return self._copy(self._plain().with_method(method))

    @override
    def with_uri(self, uri: UriInterface, preserve_host: bool = False) -> Self:
        """Return a plain copy for ``uri``, keeping a ``Host`` header where asked to."""
        return self._copy(self._plain().with_uri(uri, preserve_host))

    @override
    def with_request_target(self, request_target: str) -> Self:
        """Return a plain copy carrying ``request_target`` exactly as given."""
        return self._copy(self._plain().with_request_target(request_target))

    # ─── what reached the application with it ──────────────────────────

    @override
    def with_cookie_params(self, cookies: Mapping[str, str]) -> Self:
        """Return a plain copy carrying ``cookies``."""
        return self._copy(self._plain().with_cookie_params(cookies))

    @override
    def with_query_params(self, query: Mapping[str, object]) -> Self:
        """Return a plain copy carrying ``query``."""
        return self._copy(self._plain().with_query_params(query))

    @override
    def with_uploaded_files(self, uploaded_files: Mapping[str, object]) -> Self:
        """Return a plain copy carrying ``uploaded_files``."""
        return self._copy(self._plain().with_uploaded_files(uploaded_files))

    @override
    def with_parsed_body(self, data: object | None) -> Self:
        """Return a plain copy carrying ``data`` as its body parameters."""
        return self._copy(self._plain().with_parsed_body(data))

    @override
    def with_attribute(self, name: str, value: object) -> Self:
        """Return a plain copy carrying one more attribute."""
        return self._copy(self._plain().with_attribute(name, value))

    @override
    def without_attribute(self, name: str) -> Self:
        """Return a plain copy with the ``name`` attribute gone."""
        return self._copy(self._plain().without_attribute(name))
