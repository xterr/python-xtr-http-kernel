"""The one seam that reads an application's routes, on either framework shape.

Releases that offer the effective view of every route are asked for it; the
rest hand their routes over already effective. Both paths are exercised here
against the installed release, the older one by taking the newer one's entry
point away.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import routing as fastapi_routing
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import BaseRoute, Host, Match, Mount, Route, Router, WebSocketRoute

from xtr_http_kernel.command._route_contexts import route_contexts

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


@pytest.fixture
def without_the_effective_view(monkeypatch: pytest.MonkeyPatch) -> None:
    """Take away the entry point the newer releases offer."""
    monkeypatch.delattr(fastapi_routing, "iter_route_contexts", raising=False)


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


@pytest.mark.usefixtures("without_the_effective_view")
def test_without_the_effective_view_the_routes_are_read_as_they_come() -> None:
    read = route_contexts(ROUTES)

    assert [(view.path, view.name, view.methods) for view in read] == [
        ("/books/{isbn}", "endpoint", {"GET", "HEAD"}),
        ("/live", "live", None),
        ("/inner", "inner", None),
        (None, "host", None),
        (None, None, None),
    ]


@pytest.mark.usefixtures("without_the_effective_view")
def test_without_the_effective_view_a_route_still_answers_a_request() -> None:
    view = route_contexts(ROUTES)[0]

    assert view.matches(_scope("/books/123"))[0] is Match.FULL
    assert view.matches(_scope("/books/123", "DELETE"))[0] is Match.PARTIAL
    assert view.matches(_scope("/nope"))[0] is Match.NONE
