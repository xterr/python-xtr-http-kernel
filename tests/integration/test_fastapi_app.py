"""A FastAPI application served from a kernel: one setup call, the framework untouched.

Requests go straight at the application through an ASGI transport; the
lifespan is entered explicitly by the ``serving`` harness, the way a server
would, and its state bridged into every request scope.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Annotated, cast

import anyio
import anyio.lowlevel
import httpx
import pytest
from fastapi import APIRouter, Depends, FastAPI, Request, Response, WebSocket
from starlette.middleware.cors import CORSMiddleware
from xtr_dependency_injection import Autowire, Injected, Kernel, Target
from xtr_dependency_injection.exception import FastapiIntegrationError

from tests.fixtures.served_app import services
from tests.fixtures.served_app.services import Greeter, RequestUnit, Tracked
from tests.support.bundles import STAMPS_SCOPE_KEY, Channel, ServedBundle
from tests.support.serving import serving
from xtr_http_kernel import setup
from xtr_http_kernel.testing import override_services

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable

    from starlette.types import Message

pytestmark = pytest.mark.anyio

GUARDED: list[str] = []
"""What the router-level dependency computed from its injected service."""


@pytest.fixture(autouse=True)
def clear_journals() -> None:
    services.LIVE_UNITS.clear()
    services.TRACKED_STEPS.clear()
    GUARDED.clear()


def _kernel(*, concurrent_scoped_access: bool = False) -> Kernel:
    return Kernel(
        "tests.fixtures.served_app",
        env="test",
        bundles={ServedBundle: {"all": True}},
        concurrent_scoped_access=concurrent_scoped_access,
    )


def _plain_dependency() -> str:
    return "real"


async def _greeting_dependency(greeter: Injected[Greeter]) -> str:
    return greeter.greet("dependency")


def _marker_routes(app: FastAPI) -> None:
    """Routes exercising every marker kind, sync and websocket included."""

    async def guard(greeter: Injected[Greeter]) -> None:
        GUARDED.append(greeter.greet("guard"))

    guarded = APIRouter(dependencies=[Depends(guard)])

    @guarded.get("/hello")
    async def hello(name: str, greeter: Injected[Greeter]) -> dict[str, str]:
        return {"greeting": greeter.greet(name)}

    app.include_router(guarded)

    @app.get("/markers")
    async def markers(
        channel: Annotated[Channel, Target("smtp")],
        environment: Annotated[str, Autowire(param="kernel.environment")],
        port: Annotated[int, Autowire(env="int:XTR_SERVED_PORT")],
    ) -> dict[str, object]:
        return {"channel": channel.name, "environment": environment, "port": port}

    @app.get("/via-depends")
    async def via_depends(made: Annotated[str, Depends(_greeting_dependency)]) -> dict[str, str]:
        return {"greeting": made}

    @app.get("/sync")
    def sync_endpoint(greeter: Injected[Greeter]) -> dict[str, str]:
        return {"greeting": greeter.greet("sync")}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket, greeter: Injected[Greeter]) -> None:
        await websocket.accept()
        name = await websocket.receive_text()
        await websocket.send_text(greeter.greet(name))
        await websocket.close()


def _journal_routes(app: FastAPI) -> None:
    """Routes whose effects the tests read back from the journals or the scope."""

    @app.get("/ids")
    async def ids(unit: Injected[RequestUnit], greeter: Injected[Greeter]) -> dict[str, int]:
        await anyio.lowlevel.checkpoint()
        return {"unit": id(unit), "singleton": id(greeter)}

    @app.get("/tracked")
    async def tracked(resource: Injected[Tracked]) -> dict[str, str]:
        del resource
        services.TRACKED_STEPS.append("endpoint")
        return {"tracked": "yes"}

    @app.get("/boom-tracked")
    async def boom_tracked(resource: Injected[Tracked]) -> dict[str, str]:
        del resource
        services.TRACKED_STEPS.append("endpoint")
        raise RuntimeError("boom")

    @app.get("/state")
    async def state(request: Request) -> dict[str, str]:
        return {"marker": cast("str", request.state.marker)}

    @app.get("/stamps")
    async def stamps(request: Request) -> dict[str, list[str]]:
        return {"stamps": cast("list[str]", request.scope.get(STAMPS_SCOPE_KEY, []))}

    @app.get("/overridable")
    async def overridable(value: Annotated[str, Depends(_plain_dependency)]) -> dict[str, str]:
        return {"value": value}


def _application(kernel: Kernel) -> FastAPI:
    """A FastAPI application written as the framework documents it, plus one setup call.

    Routes, router dependencies and other middleware are all registered
    BEFORE ``setup`` — the order the setup call promises to work with.
    """

    @asynccontextmanager
    async def app_lifespan(_app: FastAPI) -> AsyncGenerator[dict[str, str], None]:
        yield {"marker": "from-the-app"}

    app = FastAPI(lifespan=app_lifespan)
    _marker_routes(app)
    _journal_routes(app)

    @app.middleware("http")
    async def user_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["x-user-middleware"] = "ran"
        return response

    app.add_middleware(CORSMiddleware, allow_origins=["*"])
    setup(app, kernel)
    return app


async def test_every_marker_kind_resolves_in_a_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XTR_SERVED_PORT", "8767")
    app = _application(_kernel())

    async with serving(app) as client:
        greeting = await client.get("/hello", params={"name": "ada"})
        markers = await client.get("/markers")

    assert greeting.status_code == 200
    assert greeting.json() == {"greeting": "hello ada!"}
    assert markers.status_code == 200
    assert markers.json() == {"channel": "smtp", "environment": "test", "port": 8767}


async def test_injected_inside_a_depends_function_resolves() -> None:
    app = _application(_kernel())

    async with serving(app) as client:
        response = await client.get("/via-depends")

    assert response.status_code == 200
    assert response.json() == {"greeting": "hello dependency!"}


async def test_injected_in_router_level_dependencies_resolves() -> None:
    app = _application(_kernel())

    async with serving(app) as client:
        response = await client.get("/hello", params={"name": "ada"})

    assert response.status_code == 200
    assert GUARDED == ["hello guard!"]


async def test_a_sync_endpoint_resolves_markers() -> None:
    app = _application(_kernel())

    async with serving(app) as client:
        response = await client.get("/sync")

    assert response.status_code == 200
    assert response.json() == {"greeting": "hello sync!"}


async def test_a_websocket_endpoint_resolves_markers() -> None:
    app = _application(_kernel())
    sent: list[Message] = []
    incoming = iter(
        [
            {"type": "websocket.connect"},
            {"type": "websocket.receive", "text": "socket"},
            {"type": "websocket.disconnect", "code": 1000},
        ]
    )

    async def receive() -> Message:
        return next(incoming)

    async def send(message: Message) -> None:
        sent.append(message)

    async with app.router.lifespan_context(app):
        scope: dict[str, object] = {
            "type": "websocket",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "path": "/ws",
            "raw_path": b"/ws",
            "root_path": "",
            "query_string": b"",
            "headers": [(b"host", b"served.test")],
            "client": ("127.0.0.1", 51234),
            "server": ("served.test", 80),
            "subprotocols": [],
            "state": {},
        }
        await app(scope, receive, send)

    texts = [message.get("text") for message in sent if message["type"] == "websocket.send"]
    assert texts == ["hello socket!"]


async def test_user_middleware_and_cors_still_run() -> None:
    app = _application(_kernel())

    async with serving(app) as client:
        response = await client.get(
            "/hello", params={"name": "ada"}, headers={"origin": "http://elsewhere.test"}
        )

    assert response.status_code == 200
    assert response.headers["x-user-middleware"] == "ran"
    assert response.headers["access-control-allow-origin"] == "*"


async def test_the_app_lifespan_state_reaches_the_request() -> None:
    app = _application(_kernel())

    async with serving(app) as client:
        response = await client.get("/state")

    assert response.status_code == 200
    assert response.json() == {"marker": "from-the-app"}


async def test_user_dependency_overrides_still_work() -> None:
    app = _application(_kernel())
    app.dependency_overrides[_plain_dependency] = lambda: "overridden"

    async with serving(app) as client:
        response = await client.get("/overridable")

    assert response.json() == {"value": "overridden"}


async def test_openapi_lists_only_http_parameters() -> None:
    app = _application(_kernel())

    schema = app.openapi()

    paths = cast("dict[str, dict[str, dict[str, object]]]", schema["paths"])
    hello = paths["/hello"]["get"]
    parameters = cast("list[dict[str, object]]", hello["parameters"])
    assert [parameter["name"] for parameter in parameters] == ["name"]
    assert "requestBody" not in hello
    markers = paths["/markers"]["get"]
    assert markers.get("parameters", []) == []


async def test_twenty_concurrent_requests_get_their_own_scoped_unit() -> None:
    app = _application(_kernel(concurrent_scoped_access=True))
    singletons: list[int] = []

    async with serving(app) as client:

        async def one_request() -> None:
            response = await client.get("/ids")
            assert response.status_code == 200
            singletons.append(cast("int", response.json()["singleton"]))

        async with anyio.create_task_group() as group:
            for _ in range(20):
                _ = group.start_soon(one_request)

    assert len(services.LIVE_UNITS) == 20
    assert len({id(unit) for unit in services.LIVE_UNITS}) == 20
    assert len(set(singletons)) == 1


async def test_a_scoped_resources_cleanup_runs_after_the_response_left() -> None:
    app = _application(_kernel())

    async with serving(
        app, on_response_sent=lambda: services.TRACKED_STEPS.append("response sent")
    ) as client:
        response = await client.get("/tracked")

    assert response.status_code == 200
    assert services.TRACKED_STEPS == ["open", "endpoint", "response sent", "cleanup"]


async def test_two_application_lives_in_one_test_each_get_a_fresh_kernel() -> None:
    app = _application(_kernel())

    async with serving(app) as client:
        first = await client.get("/ids")
    async with serving(app) as client:
        second = await client.get("/ids")

    assert first.status_code == 200
    assert second.status_code == 200
    # A fresh kernel per application life: the singleton is a new instance.
    assert first.json()["singleton"] != second.json()["singleton"]


async def test_setup_called_after_routers_and_other_middleware_serves() -> None:
    # ``_application`` registers every route, the router-level dependency and
    # both middlewares before its one ``setup`` call; serving still works.
    app = _application(_kernel())

    async with serving(app) as client:
        response = await client.get("/hello", params={"name": "late"})

    assert response.status_code == 200
    assert response.json() == {"greeting": "hello late!"}


async def test_a_marker_in_an_application_without_setup_answers_500() -> None:
    app = FastAPI()

    @app.get("/hello")
    async def hello(greeter: Injected[Greeter]) -> dict[str, str]:
        return {"greeting": greeter.greet("nobody")}

    swallowing = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=swallowing, base_url="http://served.test") as client:
        response = await client.get("/hello")
    assert response.status_code == 500

    raising = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=raising, base_url="http://served.test") as client:
        with pytest.raises(FastapiIntegrationError, match=r"xtr_http_kernel\.setup"):
            _ = await client.get("/hello")


async def test_contributed_middleware_wraps_requests_in_priority_order() -> None:
    app = _application(_kernel())

    async with serving(app) as client:
        response = await client.get("/stamps")

    # Highest priority outermost — so it runs first on the way in.
    assert response.json() == {"stamps": ["outer", "plain", "inner"]}


async def test_override_services_swaps_a_service_for_one_application_life() -> None:
    app = _application(_kernel())

    class Fake:
        def greet(self, name: str) -> str:
            return f"faked {name}"

    with override_services(app, {Greeter: Fake()}):
        async with serving(app) as client:
            overridden = await client.get("/hello", params={"name": "ada"})

    async with serving(app) as client:
        real = await client.get("/hello", params={"name": "ada"})

    assert overridden.json() == {"greeting": "faked ada"}
    assert real.json() == {"greeting": "hello ada!"}


async def test_a_raising_endpoint_still_closes_the_scope() -> None:
    app = _application(_kernel())

    async with serving(app) as client:
        failed = await client.get("/boom-tracked")
        after = await client.get("/hello", params={"name": "ada"})

    assert failed.status_code == 500
    assert services.TRACKED_STEPS == ["open", "endpoint", "cleanup"]
    assert after.status_code == 200
