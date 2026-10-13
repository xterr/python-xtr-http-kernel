"""Importing a resource's routes, arranged as asked."""

from __future__ import annotations

import pytest

from tests.unit.routing.loader.configurator.support import books, paths
from xtr_http_kernel.routing import InvalidArgumentError, RouteCollection
from xtr_http_kernel.routing.loader.configurator import ImportConfigurator


def test_an_import_adds_the_routes_as_they_came() -> None:
    collection = RouteCollection()

    ImportConfigurator("books", books(), prefixable=True).apply_to(collection)

    assert paths(collection) == {"list": "/books", "show": "/books/{book_id}"}


def test_an_import_arranges_the_routes_as_asked() -> None:
    collection = RouteCollection()

    (
        ImportConfigurator("books", books(), prefixable=True)
        .prefix("/shop")
        .name_prefix("shop_")
        .exclude("show")
        .apply_to(collection)
    )

    assert paths(collection) == {"shop_list": "/shop/books"}


def test_an_import_leaves_the_offered_routes_untouched() -> None:
    offered = books()

    ImportConfigurator("books", offered, prefixable=True).prefix("/shop").apply_to(
        RouteCollection()
    )

    assert paths(offered) == {"list": "/books", "show": "/books/{book_id}"}


def test_a_prefix_on_fixed_routes_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match='"books" are at a place a standard fixes'):
        _ = ImportConfigurator("books", books(), prefixable=False).prefix("/shop")


def test_a_blank_prefix_on_fixed_routes_is_accepted() -> None:
    collection = RouteCollection()

    ImportConfigurator("books", books(), prefixable=False).prefix("/").apply_to(collection)

    assert paths(collection)["list"] == "/books"


def test_leaving_out_a_route_the_resource_lacks_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="include no 'missing'"):
        _ = ImportConfigurator("books", books(), prefixable=True).exclude("missing")
