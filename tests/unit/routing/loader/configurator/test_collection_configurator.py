"""Groups of routes under one path prefix and one name prefix."""

from __future__ import annotations

from tests.unit.routing.loader.configurator.support import endpoint, paths
from xtr_http_kernel.routing import RouteCollection
from xtr_http_kernel.routing.loader.configurator import CollectionConfigurator


def test_a_group_puts_its_routes_under_its_prefixes() -> None:
    collection = RouteCollection()
    group = CollectionConfigurator("admin_").prefix("/admin")
    _ = group.add("users", "/users").endpoint(endpoint)
    _ = group.alias("people", "users")

    group.apply_to(collection)

    assert paths(collection) == {"admin_users": "/admin/users"}
    assert collection.get("admin_people") == collection.get("admin_users")


def test_groups_nest() -> None:
    collection = RouteCollection()
    outer = CollectionConfigurator("api_").prefix("/api")
    inner = outer.collection("v1_").prefix("/v1")
    _ = inner.add("books", "/books").endpoint(endpoint)

    outer.apply_to(collection)

    assert paths(collection) == {"api_v1_books": "/api/v1/books"}


def test_a_group_without_prefixes_adds_its_routes_as_they_are() -> None:
    collection = RouteCollection()
    group = CollectionConfigurator()
    _ = group.add("books", "/books").endpoint(endpoint)

    group.apply_to(collection)

    assert paths(collection) == {"books": "/books"}
