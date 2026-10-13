"""What a routes file receives: recorded calls, applied in order when it returns."""

from __future__ import annotations

import pytest

from tests.unit.routing.loader.configurator.support import books, endpoint, paths
from xtr_http_kernel.routing import InvalidArgumentError, RouteCollection
from xtr_http_kernel.routing.loader.configurator import RoutingConfigurator


def _configurator() -> RoutingConfigurator:
    return RoutingConfigurator({"books": books()}, frozenset())


def test_nothing_reaches_the_table_until_the_file_is_applied() -> None:
    configurator = _configurator()
    _ = configurator.import_("books")
    collection = RouteCollection()

    assert len(collection) == 0
    configurator.apply(collection)

    assert paths(collection) == {"list": "/books", "show": "/books/{book_id}"}


def test_a_route_defined_after_an_import_replaces_the_imported_one() -> None:
    configurator = _configurator()
    _ = configurator.import_("books")
    _ = configurator.add("list", "/library")
    collection = RouteCollection()

    configurator.apply(collection)

    assert paths(collection)["list"] == "/library"


def test_imported_and_skipped_resources_are_mentioned() -> None:
    configurator = RoutingConfigurator({"books": books(), "shelf": books()}, frozenset())
    _ = configurator.import_("books")
    configurator.skip("shelf")

    assert configurator.mentioned == {"books", "shelf"}


def test_a_fixed_resource_cannot_be_prefixed() -> None:
    configurator = RoutingConfigurator({"books": books()}, frozenset({"books"}))

    with pytest.raises(InvalidArgumentError, match="standard fixes"):
        _ = configurator.import_("books").prefix("/shop")


def test_importing_an_unknown_resource_is_refused_naming_the_known_ones() -> None:
    configurator = _configurator()

    with pytest.raises(InvalidArgumentError, match="the known ones are 'books'"):
        _ = configurator.import_("shop")


def test_skipping_an_unknown_resource_is_refused_too() -> None:
    configurator = _configurator()

    with pytest.raises(InvalidArgumentError, match="the known ones are 'books'"):
        configurator.skip("shop")


def test_with_no_resource_offered_the_refusal_says_so() -> None:
    configurator = RoutingConfigurator({}, frozenset())

    with pytest.raises(InvalidArgumentError, match="the known ones are none"):
        configurator.skip("books")


def test_routes_aliases_and_groups_are_applied_in_the_order_written() -> None:
    configurator = RoutingConfigurator({}, frozenset())
    _ = configurator.add("home", "/").endpoint(endpoint)
    _ = configurator.alias("start", "home")
    _ = configurator.collection("admin_").add("users", "/admin/users").endpoint(endpoint)
    collection = RouteCollection()

    configurator.apply(collection)

    assert paths(collection) == {"home": "/", "admin_users": "/admin/users"}
    assert collection.get("start") == collection.get("home")
