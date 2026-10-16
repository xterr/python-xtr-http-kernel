"""What the bundle registers so a request and a response arrive as messages.

Kept apart from the bundle itself: this is the whole of the bridge's wiring,
and the two factories it registers are the only code here that runs while a
request is being served.
"""

from __future__ import annotations

# Read at runtime: the container keys a factory by what it is annotated to
# yield, so this annotation is evaluated when the definitions are emitted.
from collections.abc import AsyncIterator  # noqa: TC003 — read at runtime, see above.
from typing import TYPE_CHECKING, Final, cast

from starlette.requests import Request
from xtr_dependency_injection.integration.fastapi import current_connection
from xtr_http_message.factory import HttpFactory

# Read at runtime, as above: these annotate the factory parameters the
# container fills and the interfaces the factories are keyed by.
from xtr_http_message_contracts import (
    MessageInterface,
    RequestInterface,
    ResponseInterface,
    ServerRequestInterface,
)
from xtr_http_message_contracts.factory import (
    RequestFactoryInterface,
    ResponseFactoryInterface,
    ServerRequestFactoryInterface,
    StreamFactoryInterface,
    UploadedFileFactoryInterface,
    UriFactoryInterface,
)

from xtr_http_kernel.bridge import (
    HttpMessageFactory,
    HttpMessageFactoryInterface,
    Response,
    ResponseFactory,
    StarletteHttpFactory,
    StarletteHttpFactoryInterface,
)
from xtr_http_kernel.bridge._media_types import has_parsed_side
from xtr_http_kernel.bridge.served_connection import ServedConnection, served_connection_of
from xtr_http_kernel.exception import UnsupportedConnectionError

if TYPE_CHECKING:
    from xtr_dependency_injection import ServiceConfigurator

__all__ = ["register", "response", "server_request"]

_MESSAGE_FACTORIES: Final = (
    RequestFactoryInterface,
    ServerRequestFactoryInterface,
    StreamFactoryInterface,
    UploadedFileFactoryInterface,
    UriFactoryInterface,
)
"""The factories one implementation answers for, each reachable by itself."""


def register(services: ServiceConfigurator) -> None:
    """Register the bridge, and the request and response a served request has.

    One implementation answers for the five factories that build the parts of
    a message, each reachable by its own interface so an application can put
    something else behind one of them. The request and the response are
    scoped: they belong to one request, and a service that held on to either
    beyond it would be holding the wrong one.

    The three interfaces a request message satisfies all lead to the same
    build, so a parameter typed by the narrowest or the widest of them
    receives the same request.

    The response is reachable by the bridge's own class as well as by the
    contract, and both lead to the same build: an endpoint takes
    ``Injected[Response]`` and declares it returns a ``Response``, with the
    parameter and the return annotation agreeing, while a library that knows
    only ``ResponseInterface`` is handed that very response.

    Args:
        services: Where the definitions go.
    """
    _ = services.set(HttpFactory)
    for factory in _MESSAGE_FACTORIES:
        services.alias(factory, HttpFactory)

    _ = services.set(ResponseFactory)
    services.alias(ResponseFactoryInterface, ResponseFactory)

    _ = services.set(HttpMessageFactory)
    services.alias(HttpMessageFactoryInterface, HttpMessageFactory)

    # Built here rather than registered as a class: its only argument is how
    # much of a body to stream at a time, which is a number, not a service.
    _ = services.instance(StarletteHttpFactory())
    services.alias(StarletteHttpFactoryInterface, StarletteHttpFactory)

    _ = services.set(server_request, lifetime="scoped")
    services.alias(RequestInterface, ServerRequestInterface)
    services.alias(MessageInterface, ServerRequestInterface)

    _ = services.set(response, lifetime="scoped")
    services.alias(Response, ResponseInterface)


async def server_request(
    message_factory: HttpMessageFactoryInterface,
) -> AsyncIterator[ServerRequestInterface]:
    """Hand out the request being served as a message, once for the request.

    The message is the one the connection parked on the request's scope
    serves — the very instance its events carried, so a service and a
    listener hold one request between them. Without the lifecycle — a
    bridge-only application — the connection is built here from the
    framework's own request object, and parked in its turn.

    A body that has a parsed side — a form, JSON — is materialised before the
    message is handed on: a consumer written against the contract reads
    ``get_parsed_body()`` without reading the stream first, and this is the
    seam that can still await — so what the contract promises
    unconditionally is true by the time anything asks it. A body with no
    parsed side is left unread, and an endpoint that injects nothing reads
    the wire itself, untouched.

    A form the served request parsed is closed as the request's scope ends —
    the same moment the framework closes a form it parsed itself, and
    idempotent with the lifecycle's own close at the request's exit — so the
    files that came with the request stay open for as long as the request
    does.

    Args:
        message_factory: What builds the served request out of the connection.

    Yields:
        The request, as a message.

    Raises:
        UnsupportedConnectionError: When a socket is being served: a request
            message describes an HTTP request, and a socket is not one.
    """
    framework_request = current_connection()
    if not isinstance(framework_request, Request):
        raise UnsupportedConnectionError(cast("str", framework_request.scope["type"]))

    connection = served_connection_of(framework_request.scope)
    if connection is None:
        connection = ServedConnection(framework_request, message_factory)

    served = message_factory.serve(framework_request)
    try:
        if has_parsed_side(framework_request.headers.get("content-type", "")):
            await served.ensure_parsed()
        yield served
    finally:
        await connection.close()


def response(response_factory: ResponseFactoryInterface) -> ResponseInterface:
    """Build the response a served request is answered with, once for the request.

    It is the bridge's own response, so an endpoint writes a status, a header
    or a body into it as a message and returns it with nothing in between.

    Args:
        response_factory: What builds the response.

    Returns:
        The response, for the endpoint to fill in and return.
    """
    return response_factory.create_response()
