"""The bundle's listeners, seen through a booted kernel's dispatcher."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, cast

import pytest
from fastapi import FastAPI
from xtr_dependency_injection import Kernel
from xtr_event_dispatcher import EventDispatcherInterface
from xtr_logging import end_unit
from xtr_logging_contracts import LoggerInterface

from tests.support.serving import serving
from xtr_http_kernel import KernelEvents, RequestEvent, TerminateEvent, setup
from xtr_http_kernel.bundle import HttpKernelBundle

if TYPE_CHECKING:
    from collections.abc import Generator

    from starlette.requests import Request

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _close_any_unit() -> Generator[None, None, None]:
    yield
    end_unit()


def _kernel() -> Kernel:
    # No resources: the bundle's services are the whole container.
    return Kernel(
        "xtr_http_kernel.bundle",
        env="test",
        bundles={HttpKernelBundle: {"all": True}},
        resources=(),
    )


async def test_the_request_id_listener_is_registered_as_a_listener(
    http_request: Request,
) -> None:
    async with await _kernel().boot() as booted:
        dispatcher = await booted.container.get(EventDispatcherInterface)

        listeners = dispatcher.get_listeners(KernelEvents.REQUEST)
        assert any("RequestIdListener" in repr(listener) for listener in listeners)

        # Dispatching the event proves the registration reaches the listener.
        _ = await dispatcher.dispatch(RequestEvent(http_request))
        _ = await dispatcher.dispatch(TerminateEvent(http_request, 200))

    settled = cast("str", http_request.state.request_id)
    assert settled


async def test_the_log_listeners_join_when_logging_is_active() -> None:
    async with await _kernel().boot() as booted:
        dispatcher = await booted.container.get(EventDispatcherInterface)

        assert dispatcher.get_listeners(KernelEvents.EXCEPTION)
        assert dispatcher.get_listeners(KernelEvents.TERMINATE)
        # The prepend declared the request channel on the logging config.
        assert booted.container.has(LoggerInterface, "request")


async def test_without_logging_no_log_listener_exists_and_requests_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A ``None`` module entry makes the import fail, so the optional peer is
    # skipped exactly as if the logging extra were not installed.
    modules = cast("dict[str, object]", sys.modules)
    monkeypatch.setitem(modules, "xtr_logging.bundle", None)

    async with await _kernel().boot() as booted:
        dispatcher = await booted.container.get(EventDispatcherInterface)

        assert dispatcher.get_listeners(KernelEvents.EXCEPTION) == []
        assert dispatcher.get_listeners(KernelEvents.TERMINATE) == []
        assert dispatcher.get_listeners(KernelEvents.REQUEST)

    app = FastAPI()

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"ping": "pong"}

    setup(app, _kernel())
    async with serving(app) as client:
        response = await client.get("/ping")

    assert response.status_code == 200
    assert response.headers["x-request-id"]
