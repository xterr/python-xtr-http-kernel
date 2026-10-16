"""A counter on the one thing that reads a served request's body.

The bundle here puts its own implementation of the bridge's message factory
behind the interface the bundle's per-request factory and the lifecycle
middleware ask for, and that implementation delegates to the bridge's own.
The head of a served request is built for every request the lifecycle
middleware serves — that costs no input — so what the journal counts is the
part that costs: each body a served request materialises, the first time
something reads its stream. A route that never reads the body leaves the
journal empty, and nothing is buffered anywhere.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_dependency_injection import Bundle, as_bundle
from xtr_http_message import ServerRequest

# Read at runtime: the container fills the constructor parameter below, and
# keys the alias by the interface.
from xtr_http_kernel.bridge import HttpMessageFactory, HttpMessageFactoryInterface
from xtr_http_kernel.bridge.served_connection import ServedConnection, served_connection_of

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

__all__ = ["BUILT", "CountingMessages", "MessageCounterBundle"]

BUILT: Final[list[str]] = []
"""The path of every request whose body was materialised, in order."""


@final
class CountingMessages(HttpMessageFactoryInterface):
    """Journals each body a served request materialised, then has the bridge parse it.

    Materialising a body parses it per its content type through the eager
    factory, so every parse counted is a read of a body that really
    happened, inside a real container — nothing is patched, and a route that
    never reads the body leaves the journal empty.
    """

    __slots__ = ("_inner",)

    def __init__(self, message_factory: HttpMessageFactory) -> None:
        """Count the bodies the bridge reads, parsing them through ``message_factory``."""
        self._inner = message_factory

    @override
    async def create_request(self, request: Request) -> ServerRequestInterface:
        """Record the path, then return what the bridge makes of ``request``."""
        BUILT.append(request.url.path)
        return await self._inner.create_request(request)

    @override
    def create_response(self, response: Response) -> ResponseInterface:
        """Return what the bridge makes of ``response``."""
        return self._inner.create_response(response)

    @override
    def serve(self, request: Request) -> ServerRequest:
        """Serve ``request`` through the bridge, parsing its body through this."""
        if served_connection_of(request.scope) is None:
            # Park a connection that parses through this factory, so the
            # materialisations it counts are the ones this factory parses.
            _ = ServedConnection(request, self)
        return self._inner.serve(request)


@as_bundle("message_counter")
class MessageCounterBundle(Bundle[object]):
    """Puts the counting factory where the bridge's own was."""

    @override
    def load_extension(
        self, config: object, services: ServiceConfigurator, builder: ContainerBuilder
    ) -> None:
        """Register the counting factory, leaving the bridge's own in place."""
        del config, builder
        _ = services.set(CountingMessages)

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Point the message factory interface at the counting one.

        Runs once every bundle has loaded, so the alias the http_kernel
        bundle registered is there to be moved.
        """
        builder.remove_alias(HttpMessageFactoryInterface)
        builder.set_alias(HttpMessageFactoryInterface, CountingMessages)
