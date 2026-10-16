"""The head of a served request: everything read straight off the connection.

The method, the URI, the headers, the cookies, the query parameters, the
environment parameters and the protocol version cost no input — each is
already on the connection the request arrived on. This is the part of a
served request that may be built for every request the lifecycle serves,
because none of it touches the wire.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Final, cast

from ._headers import grouped_headers
from ._scope_uri import scope_uri

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from starlette.requests import Request
    from starlette.types import Scope
    from xtr_http_message_contracts import UriInterface
    from xtr_http_message_contracts.factory import UriFactoryInterface

__all__ = ["ServedHead"]

_SERVER_PARAMS: Final = (
    "type",
    "http_version",
    "method",
    "scheme",
    "path",
    "root_path",
    "query_string",
    "server",
    "client",
)
"""What the connection says about itself, as the request's environment.

A message's environment parameters are whatever the server knows about the
request besides the request itself — the connection as the server described
it, minus the entries that are the framework's own machinery, which the
message carries in its own right or has no business repeating.
"""

_DEFAULT_PROTOCOL: Final = "1.1"


def _server_params(scope: Scope) -> Mapping[str, object]:
    """Return the connection's own entries, under the names the server gave them."""
    return {key: cast("object", scope[key]) for key in _SERVER_PARAMS if key in scope}


class ServedHead:
    """The head of a served request, read off its connection as it is asked for.

    A mixin, for the same reason the message implementation's own traits are:
    the head is one part of what a served request answers, and the class
    composing it — :class:`~xtr_http_kernel.bridge.served_request.ServedRequest`
    — carries the rest.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_protocol", "_request", "_uri")

    def __init__(self, request: Request, uris: UriFactoryInterface) -> None:
        """Hold ``request``, reading its URI and its protocol version off its connection.

        Args:
            request: The request the framework is serving.
            uris: Builds the URI of the request, so the implementation stays
                the application's choice.
        """
        self._request: Request = request
        self._uri: UriInterface = scope_uri(uris, request.scope)
        self._protocol: str = cast("str", request.scope.get("http_version", _DEFAULT_PROTOCOL))

    def get_protocol_version(self) -> str:
        """Return the HTTP version of the connection."""
        return self._protocol

    def get_headers(self) -> Mapping[str, Sequence[str]]:
        """Return every header, each name mapped to all of its values."""
        return grouped_headers(self._request.headers.raw)

    def has_header(self, name: str) -> bool:
        """Tell whether a header is present, matching ``name`` without case."""
        return name in self._request.headers

    def get_header(self, name: str) -> Sequence[str]:
        """Return every value recorded under a header, matched without case."""
        return self._request.headers.getlist(name)

    def get_header_line(self, name: str) -> str:
        """Return the values of a header joined with commas, matched without case."""
        return ", ".join(self._request.headers.getlist(name))

    def get_server_params(self) -> Mapping[str, object]:
        """Return the parameters of the environment the request arrived in."""
        return _server_params(self._request.scope)

    def get_cookie_params(self) -> Mapping[str, str]:
        """Return the cookies the client sent."""
        return self._request.cookies

    def get_query_params(self) -> Mapping[str, object]:
        """Return the query string, parsed into parameters."""
        return self._request.query_params

    def get_method(self) -> str:
        """Return the HTTP method of the connection."""
        return self._request.method

    def get_uri(self) -> UriInterface:
        """Return the URI the connection arrived for."""
        return self._uri

    def get_request_target(self) -> str:
        """Return the request-target: the URI's path with its query string after it."""
        target = self._uri.get_path()
        if target == "":
            target = "/"
        query = self._uri.get_query()
        if query != "":
            target = f"{target}?{query}"
        return target
