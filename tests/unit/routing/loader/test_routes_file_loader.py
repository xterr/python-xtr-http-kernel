"""Building the table from routes files and the resources offered."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.unit.routing.loader.configurator.support import books, endpoint, paths
from xtr_http_kernel.routing import Route, RouteCollection
from xtr_http_kernel.routing.loader import RoutesFileLoader

if TYPE_CHECKING:
    from xtr_http_kernel.routing.loader.configurator import RoutingConfigurator


def _shelf() -> RouteCollection:
    routes = RouteCollection()
    routes.add("shelf", Route("/shelf", endpoint))
    return routes


def test_with_no_routes_file_every_resource_is_served_as_offered() -> None:
    table = RoutesFileLoader([]).load({"books": books(), "shelf": _shelf()})

    assert paths(table) == {"list": "/books", "show": "/books/{book_id}", "shelf": "/shelf"}


def test_unmentioned_resources_come_first_then_each_file_in_order() -> None:
    def first(routes: RoutingConfigurator) -> None:
        _ = routes.import_("books").prefix("/first").name_prefix("first_").exclude("show")

    def second(routes: RoutingConfigurator) -> None:
        _ = routes.add("home", "/").endpoint(endpoint)

    table = RoutesFileLoader([first, second]).load({"books": books(), "shelf": _shelf()})

    assert list(paths(table)) == ["shelf", "first_list", "home"]


def test_each_file_imports_the_resource_as_offered() -> None:
    def moves(routes: RoutingConfigurator) -> None:
        _ = routes.import_("books").prefix("/moved").name_prefix("moved_")

    def plain(routes: RoutingConfigurator) -> None:
        _ = routes.import_("books")

    table = RoutesFileLoader([moves, plain]).load({"books": books()})

    assert paths(table)["list"] == "/books"
    assert paths(table)["moved_list"] == "/moved/books"


def test_a_skipped_resource_is_left_out() -> None:
    def skips(routes: RoutingConfigurator) -> None:
        routes.skip("books")

    table = RoutesFileLoader([skips]).load({"books": books(), "shelf": _shelf()})

    assert paths(table) == {"shelf": "/shelf"}
