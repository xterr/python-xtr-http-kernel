"""Defining, moving and redefining one route in a routes file."""

from __future__ import annotations

import pytest

from tests.unit.routing.loader.configurator.support import books, endpoint, other_endpoint
from xtr_http_kernel.routing import InvalidArgumentError, Route, RouteCollection
from xtr_http_kernel.routing.loader.configurator import RouteConfigurator


def test_a_new_route_is_built_from_what_was_set() -> None:
    collection = RouteCollection()

    (
        RouteConfigurator("home", "/")
        .endpoint(endpoint)
        .methods("get")
        .tags("pages")
        .summary("Home")
        .status_code(201)
        .include_in_schema(include=False)
        .response_model(None)
        .apply_to(collection)
    )

    route = collection.get("home")
    assert route == Route(
        "/",
        endpoint,
        methods=("GET",),
        tags=("pages",),
        summary="Home",
        status_code=201,
        include_in_schema=False,
        response_model=None,
    )


def test_a_new_route_without_an_endpoint_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match='"home" has no endpoint'):
        RouteConfigurator("home", "/").apply_to(RouteCollection())


def test_an_existing_name_moves_its_route_keeping_the_rest() -> None:
    collection = books()

    RouteConfigurator("list", "/library").apply_to(collection)

    route = collection.get("list")
    assert route is not None
    assert (route.path, route.endpoint, route.methods) == ("/library", endpoint, ("GET",))


def test_an_existing_name_can_take_a_new_endpoint() -> None:
    collection = books()

    RouteConfigurator("list", "/books").endpoint(other_endpoint).apply_to(collection)

    route = collection.get("list")
    assert route is not None
    assert route.endpoint is other_endpoint


def test_a_redefined_route_keeps_its_priority_unless_given_one() -> None:
    collection = RouteCollection()
    collection.add("list", Route("/books", endpoint), priority=4)

    RouteConfigurator("list", "/library").apply_to(collection)
    assert collection.get_priority("list") == 4

    RouteConfigurator("list", "/library").priority(1).apply_to(collection)
    assert collection.get_priority("list") == 1


def test_moving_an_alias_moves_the_route_it_stands_for() -> None:
    collection = books()
    _ = collection.add_alias("catalogue", "list")

    RouteConfigurator("catalogue", "/library").apply_to(collection)

    route = collection.get("list")
    assert route is not None
    assert route.path == "/library"
    assert collection.get_alias("catalogue") is not None
