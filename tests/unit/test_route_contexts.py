"""The one seam that reads an application's routes, every prefix applied."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, FastAPI, WebSocket
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import BaseRoute, Host, Match, Mount, Route, Router, WebSocketRoute

from xtr_http_kernel._route_contexts import route_contexts

if TYPE_CHECKING:
    from starlette.types import Scope


async def endpoint(request: Request) -> PlainTextResponse:
    del request
    return PlainTextResponse("ok")


ROUTES: list[BaseRoute] = [
    Route("/books/{isbn}", endpoint, methods=["GET"]),
    WebSocketRoute("/live", endpoint, name="live"),
    Mount("/inner", Router(routes=[Route("/ping", endpoint)]), name="inner"),
    Host("books.test", app=Router(), name="host"),
    BaseRoute(),
]
"""One route of every kind the framework can hand over, effective as they are."""


def _scope(path: str, method: str = "GET") -> Scope:
    return {"type": "http", "method": method, "path": path, "root_path": ""}


def test_every_route_is_read_in_order() -> None:
    read = route_contexts(ROUTES)

    assert [view.route for view in read] == ROUTES


def test_a_method_route_carries_its_path_name_methods_and_endpoint() -> None:
    view = route_contexts(ROUTES)[0]

    assert view.path == "/books/{isbn}"
    assert view.name == "endpoint"
    assert view.methods == {"GET", "HEAD"}
    assert view.endpoint is endpoint


def test_a_connection_route_carries_no_methods() -> None:
    view = route_contexts(ROUTES)[1]

    assert view.path == "/live"
    assert view.name == "live"
    assert view.methods is None
    assert view.endpoint is endpoint


def test_a_mount_carries_no_endpoint() -> None:
    view = route_contexts(ROUTES)[2]

    assert view.path == "/inner"
    assert view.name == "inner"
    assert view.endpoint is None


def test_a_host_carries_its_name_alone() -> None:
    view = route_contexts(ROUTES)[3]

    assert view.path is None
    assert view.name == "host"
    assert view.methods is None
    assert view.endpoint is None


def test_a_route_the_framework_keeps_to_itself_carries_nothing() -> None:
    view = route_contexts(ROUTES)[4]

    assert view.path is None
    assert view.name is None
    assert view.methods is None
    assert view.endpoint is None


def test_a_view_answers_how_well_a_request_fits() -> None:
    view = route_contexts(ROUTES)[0]

    assert view.matches(_scope("/books/123"))[0] is Match.FULL
    assert view.matches(_scope("/books/123", "DELETE"))[0] is Match.PARTIAL
    assert view.matches(_scope("/nope"))[0] is Match.NONE


def test_a_full_match_reads_the_path_parameters_out() -> None:
    view = route_contexts(ROUTES)[0]

    _, child_scope = view.matches(_scope("/books/123"))

    assert child_scope["path_params"] == {"isbn": "123"}


def test_the_routes_of_an_included_router_are_read_at_their_prefixed_paths() -> None:
    router = APIRouter()

    @router.get("/items", name="items")
    async def items() -> None: ...

    @router.websocket("/live", name="live")
    async def live(websocket: WebSocket) -> None:
        del websocket

    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    app.include_router(router, prefix="/v1")

    read = route_contexts(app.router.routes)

    # A socket as well as a method route: the framework's effective view left
    # an included socket without its path before the release this package
    # requires.
    assert [(view.path, view.name) for view in read] == [
        ("/v1/items", "items"),
        ("/v1/live", "live"),
    ]
