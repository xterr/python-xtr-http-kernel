"""The three ways asking for the request as a message is refused.

Nothing is guessed at and nothing is handed over half-built: with no request
being served there is no request to hand over, a socket is not a request, and
a service built for the whole application could only ever hold the wrong one
— which the container says while it is being built, not once it is serving.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI, WebSocket
from xtr_dependency_injection import Injected, Kernel, ScopeFactoryInterface
from xtr_dependency_injection.exception import (
    ContainerCompilationError,
    FastapiIntegrationError,
    ServiceResolutionError,
)

# Read at runtime: the framework evaluates a route's annotations.
from xtr_http_message_contracts import ServerRequestInterface

from tests.support.bundles import RequestReaderBundle
from tests.support.message_apps import message_kernel
from tests.support.serving import driving
from xtr_http_kernel import setup
from xtr_http_kernel.bundle import HttpKernelBundle
from xtr_http_kernel.exception import UnsupportedConnectionError

if TYPE_CHECKING:
    from starlette.types import Message, Receive

pytestmark = pytest.mark.anyio

_SOCKET_SCOPE: dict[str, object] = {
    "type": "websocket",
    "asgi": {"version": "3.0", "spec_version": "2.3"},
    "path": "/socket",
    "raw_path": b"/socket",
    "root_path": "",
    "query_string": b"",
    "headers": [(b"host", b"served.test")],
    "client": ("127.0.0.1", 51234),
    "server": ("served.test", 80),
    "subprotocols": [],
}


def _socket_application() -> FastAPI:
    app = FastAPI()

    @app.websocket("/socket")
    async def socket(websocket: WebSocket, message: Injected[ServerRequestInterface]) -> None:
        del message
        await websocket.close()

    setup(app, message_kernel())
    return app


def _connecting() -> Receive:
    """Return a receive channel offering one socket connection."""
    incoming = iter(({"type": "websocket.connect"}, {"type": "websocket.disconnect", "code": 1000}))

    async def receive() -> Message:
        return next(incoming, {"type": "websocket.disconnect", "code": 1000})

    return receive


async def test_asking_with_no_request_being_served_says_so() -> None:
    async with await message_kernel().boot() as booted:
        scopes = await booted.container.get(ScopeFactoryInterface)
        async with scopes.unit_of_work(join=False) as unit:
            with pytest.raises(ServiceResolutionError, match="while a request is served") as raised:
                _ = await unit.get(ServerRequestInterface)

    # The container reports which service it could not build; what it could
    # not do is the integration's own refusal, carried as the cause.
    assert isinstance(raised.value.__cause__, FastapiIntegrationError)


async def test_asking_while_a_socket_is_served_refuses_the_connection() -> None:
    async with driving(_socket_application()) as drive:
        with pytest.raises(UnsupportedConnectionError, match="websocket"):
            _ = await drive(dict(_SOCKET_SCOPE), _connecting())


def test_a_singleton_asking_for_the_request_fails_at_setup() -> None:
    app = FastAPI()

    @app.get("/plain")
    async def plain() -> dict[str, str]:
        return {"plain": "yes"}

    # setup() compiles the kernel to read its routes, so the refusal comes here.
    with pytest.raises(ContainerCompilationError, match="Singletons can only depend on"):
        setup(
            app,
            Kernel(
                "tests.fixtures.message_app",
                env="test",
                bundles={HttpKernelBundle: {"all": True}, RequestReaderBundle: {"all": True}},
            ),
        )
