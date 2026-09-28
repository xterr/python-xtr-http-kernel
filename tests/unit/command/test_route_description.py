"""Unit tests for :class:`xtr_http_kernel.command.route_description.RouteDescription`."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import BaseRoute, Host, Mount, Route, Router, WebSocketRoute

from tests.fixtures.router_app.app import app
from tests.support.route_listing import lists_included_routers
from xtr_http_kernel.command._route_contexts import RouteView, route_contexts
from xtr_http_kernel.command.route_description import RouteDescription


def view(route: BaseRoute) -> RouteView:
    """Read one route the way the commands do."""
    return route_contexts([route])[0]


async def endpoint(request: Request) -> PlainTextResponse:
    del request
    return PlainTextResponse("ok")


class AsgiEndpoint:
    """A class endpoint: routing treats it as an application, not a handler."""

    def __init__(self, scope: object) -> None:
        self.scope: object = scope


class Handler:
    async def handle(self, request: Request) -> PlainTextResponse:
        del request
        return PlainTextResponse("ok")


def test_a_route_is_described_by_its_methods_path_name_and_endpoint() -> None:
    described = RouteDescription.of(view(Route("/books/{isbn}", endpoint, methods=["GET"])))

    assert described.methods == "GET, HEAD"
    assert described.path == "/books/{isbn}"
    assert described.name == "endpoint"
    assert described.endpoint == f"{__name__}:endpoint"


def test_a_route_answering_whatever_arrives_names_no_method() -> None:
    described = RouteDescription.of(view(Route("/any", AsgiEndpoint)))

    assert described.methods == "-"
    assert described.endpoint == f"{__name__}:AsgiEndpoint"


def test_a_bound_method_endpoint_is_named_by_its_class_and_method() -> None:
    described = RouteDescription.of(view(Route("/handled", Handler().handle)))

    assert described.endpoint == f"{__name__}:Handler.handle"


def test_a_connection_route_is_described_as_one() -> None:
    described = RouteDescription.of(view(WebSocketRoute("/live", endpoint, name="live")))

    assert described.methods == "WEBSOCKET"
    assert described.name == "live"
    assert described.endpoint == f"{__name__}:endpoint"


def test_a_mount_is_described_by_the_application_it_carries() -> None:
    described = RouteDescription.of(view(Mount("/inner", Router(), name="inner")))

    assert described.methods == "MOUNT"
    assert described.path == "/inner"
    assert described.name == "inner"
    assert described.endpoint == "starlette.routing:Router"


def test_a_route_with_nothing_to_call_is_named_by_itself() -> None:
    described = RouteDescription.of(view(Host("books.test", app=Router())))

    assert described.methods == "-"
    assert described.path == ""
    assert described.name == ""
    assert described.endpoint == "starlette.routing:Host"


@lists_included_routers
def test_an_application_is_described_route_by_route_with_prefixes_applied() -> None:
    described = {
        description.path: description
        for description in (RouteDescription.of(read) for read in route_contexts(app.routes))
    }

    assert described["/books/{isbn}"].methods == "GET"
    assert described["/books/{isbn}"].name == "book"
    assert described["/books/{isbn}"].endpoint == "tests.fixtures.router_app.app:book"
    assert described["/orders"].methods == "POST"
    assert described["/live"].methods == "WEBSOCKET"
    assert described["/inner"].methods == "MOUNT"
