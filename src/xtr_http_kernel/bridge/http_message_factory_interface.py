"""Turning the framework's own request and response into HTTP messages."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from .served_request import ServedRequest

__all__ = ["HttpMessageFactoryInterface"]


@runtime_checkable
class HttpMessageFactoryInterface(Protocol):
    """Builds HTTP messages from what the web framework is holding.

    One direction of the bridge: a library written against the message
    contract is handed what the framework already read off the wire, rather
    than reading it a second time.
    """

    def serve(self, request: Request) -> ServedRequest:
        """Return ``request`` as a served request: a read-through view over its connection.

        Unlike :meth:`create_request`, nothing is read: the head is built
        from the connection alone, and the body is one lazy stream that
        materialises the first time anything reads it. This is the message
        the request lifecycle hands its events, so that a listener may look
        at a request without the cost of reading it.

        Args:
            request: The request the framework is serving.

        Returns:
            The same request, as a message nothing has read the body of.
        """
        ...

    async def create_request(self, request: Request) -> ServerRequestInterface:
        """Return ``request`` as a server request message.

        Awaits, because a body and a form are read asynchronously — from
        whatever the framework has already cached, so nothing is taken off the
        wire twice.

        Args:
            request: The request the framework is serving.

        Returns:
            The same request, as a message.
        """
        ...

    def create_response(self, response: Response) -> ResponseInterface:
        """Return ``response`` as a response message.

        Args:
            response: The response the framework would send.

        Returns:
            The same response, as a message.
        """
        ...
