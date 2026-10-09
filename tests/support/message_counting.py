"""A counter on the one thing that builds a request message.

The bundle here puts its own implementation of the bridge's message factory
behind the interface the bundle's per-request factory asks for, and that
implementation delegates to the bridge's own. So every build counted is a
build that really happened inside a real container — nothing is patched, and
a route that never asks for the request leaves the journal empty.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_dependency_injection import Bundle, as_bundle

# Read at runtime: the container fills the constructor parameter below, and
# keys the alias by the interface.
from xtr_http_kernel.bridge import HttpMessageFactory, HttpMessageFactoryInterface

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

__all__ = ["BUILT", "CountingMessages", "MessageCounterBundle"]

BUILT: Final[list[str]] = []
"""The path of every request that was built as a message, in order."""


@final
class CountingMessages(HttpMessageFactoryInterface):
    """Journals each request built as a message, then has the bridge build it."""

    __slots__ = ("_inner",)

    def __init__(self, inner: HttpMessageFactory) -> None:
        self._inner = inner

    @override
    async def create_request(self, request: Request) -> ServerRequestInterface:
        """Record the path, then return what the bridge makes of ``request``."""
        BUILT.append(request.url.path)
        return await self._inner.create_request(request)

    @override
    def create_response(self, response: Response) -> ResponseInterface:
        """Return what the bridge makes of ``response``."""
        return self._inner.create_response(response)


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
