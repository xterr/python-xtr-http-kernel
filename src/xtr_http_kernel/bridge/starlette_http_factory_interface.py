"""Turning HTTP messages back into what the web framework serves."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

__all__ = ["StarletteHttpFactoryInterface"]


@runtime_checkable
class StarletteHttpFactoryInterface(Protocol):
    """Builds the framework's own request and response out of HTTP messages.

    The other direction of the bridge: a message made elsewhere — by a library
    that knows only the contract, or by a test — becomes something the
    framework can route or send.
    """

    def create_request(
        self,
        server_request: ServerRequestInterface,
        streamed: bool = False,
    ) -> Request:
        """Return ``server_request`` as a request the framework can serve.

        Args:
            server_request: The request message.
            streamed: Whether the body is handed over in chunks as it is
                asked for rather than read whole up front.

        Returns:
            The same request, as the framework's own.
        """
        ...

    def create_response(
        self,
        response: ResponseInterface,
        streamed: bool = False,
    ) -> Response:
        """Return ``response`` as a response the framework can send.

        Args:
            response: The response message.
            streamed: Whether the body goes out in chunks rather than whole.

        Returns:
            The same response, as the framework's own.
        """
        ...
