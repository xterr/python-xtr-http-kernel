"""Who may ask for the request as a message, and how often it is built.

A per-request service takes it through its constructor, a route takes it as a
parameter, a dependency of a route takes it too — and whichever of them asks,
and however many of them ask, one request is built once and all of them hold
that one. None of it depends on the endpoint being a coroutine.
"""

from __future__ import annotations

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from xtr_dependency_injection import Injected

# Read at runtime: the framework evaluates a route's annotations.
from xtr_http_message_contracts import ServerRequestInterface

from tests.fixtures.message_app.services import BUILDS, RequestAudit
from tests.support.message_apps import message_kernel
from tests.support.message_counting import BUILT
from tests.support.serving import serving
from xtr_http_kernel import setup

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _clear_journals() -> None:
    BUILT.clear()
    BUILDS.clear()


def _message_path(message: Injected[ServerRequestInterface]) -> str:
    """A dependency of a route, declared with ``def`` rather than ``async def``."""
    return message.get_uri().get_path()


def _application() -> FastAPI:
    app = FastAPI()

    @app.get("/audited")
    async def audited(
        audit: Injected[RequestAudit], message: Injected[ServerRequestInterface]
    ) -> dict[str, object]:
        return {"same": audit.request is message, "path": audit.path()}

    @app.get("/service-only")
    async def service_only(audit: Injected[RequestAudit]) -> dict[str, str]:
        return {"path": audit.path()}

    @app.get("/sync")
    def sync_route(message: Injected[ServerRequestInterface]) -> dict[str, str]:
        return {"path": message.get_uri().get_path()}

    @app.get("/sync-dependency")
    async def sync_dependency(path: Annotated[str, Depends(_message_path)]) -> dict[str, str]:
        return {"path": path}

    setup(app, message_kernel())
    return app


async def test_a_service_and_the_route_hold_the_same_request_built_once() -> None:
    async with serving(_application()) as client:
        response = await client.get("/audited")

    assert response.json() == {"same": True, "path": "/audited"}
    assert BUILT == ["/audited"]
    assert len(BUILDS) == 1


async def test_a_service_alone_is_enough_to_have_the_request_built() -> None:
    async with serving(_application()) as client:
        response = await client.get("/service-only")

    assert response.json() == {"path": "/service-only"}
    assert BUILT == ["/service-only"]


async def test_a_sync_endpoint_is_handed_the_request() -> None:
    async with serving(_application()) as client:
        response = await client.get("/sync")

    assert response.json() == {"path": "/sync"}
    assert BUILT == ["/sync"]


async def test_a_sync_dependency_of_a_route_is_handed_the_request() -> None:
    async with serving(_application()) as client:
        response = await client.get("/sync-dependency")

    assert response.json() == {"path": "/sync-dependency"}
    assert BUILT == ["/sync-dependency"]


async def test_two_requests_each_get_their_own_message_and_audit() -> None:
    async with serving(_application()) as client:
        first = await client.get("/audited")
        second = await client.get("/service-only")

    assert (first.status_code, second.status_code) == (200, 200)
    assert BUILT == ["/audited", "/service-only"]
    assert len(set(BUILDS)) == 2
