"""The route collection: order, priority, prefixes, aliases and removal."""

from __future__ import annotations

import pytest

from xtr_http_kernel.routing import (
    InvalidArgumentError,
    Route,
    RouteCircularReferenceError,
    RouteCollection,
)


async def _endpoint() -> dict[str, str]:
    return {}


def _route(path: str) -> Route:
    return Route(path, _endpoint)


def _collection(*names: str) -> RouteCollection:
    collection = RouteCollection()
    for name in names:
        collection.add(name, _route(f"/{name}"))
    return collection


def test_routes_come_back_in_declaration_order() -> None:
    assert list(_collection("a", "b", "c").all()) == ["a", "b", "c"]


def test_adding_a_name_again_replaces_its_route_and_moves_it_to_the_end() -> None:
    collection = _collection("a", "b")

    collection.add("a", _route("/again"))

    assert list(collection.all()) == ["b", "a"]
    assert collection.all()["a"].path == "/again"


def test_a_higher_priority_comes_first_and_equal_priorities_keep_declaration_order() -> None:
    collection = RouteCollection()
    collection.add("low", _route("/low"))
    collection.add("first_high", _route("/h1"), priority=5)
    collection.add("other", _route("/other"))
    collection.add("second_high", _route("/h2"), priority=5)
    collection.add("negative", _route("/n"), priority=-1)

    assert list(collection.all()) == ["first_high", "second_high", "low", "other", "negative"]
    assert collection.get_priority("first_high") == 5
    assert collection.get_priority("low") is None


def test_iterating_yields_names_and_routes_in_order() -> None:
    collection = _collection("a", "b")

    assert [(name, route.path) for name, route in collection] == [("a", "/a"), ("b", "/b")]
    assert len(collection) == 2


def test_get_returns_a_route_by_name_or_none() -> None:
    collection = _collection("a")

    assert collection.get("a") == _route("/a")
    assert collection.get("missing") is None


def test_get_follows_a_chain_of_aliases() -> None:
    collection = _collection("books")
    _ = collection.add_alias("shelf", "books")
    _ = collection.add_alias("old_shelf", "shelf")

    assert collection.get("old_shelf") == _route("/books")


def test_aliases_looping_back_are_refused_naming_the_loop() -> None:
    collection = RouteCollection()
    _ = collection.add_alias("a", "b")
    _ = collection.add_alias("b", "a")
    _ = collection.add_alias("x", "a")

    with pytest.raises(RouteCircularReferenceError) as caught:
        _ = collection.get("x")

    assert (caught.value.name, caught.value.path) == ("a", ("a", "b", "a"))
    assert str(caught.value) == 'Circular reference detected for route "a", path: "a -> b -> a".'


def test_a_deprecated_alias_warns_when_it_is_followed() -> None:
    collection = _collection("books")
    _ = collection.add_alias("old", "books").set_deprecated(
        "acme/shop", "2.0", 'Use "books", not "%alias_id%".'
    )

    with pytest.warns(
        DeprecationWarning, match=r'^Since acme/shop 2\.0: Use "books", not "old"\.$'
    ):
        _ = collection.get("old")


def test_a_deprecation_naming_no_package_or_version_warns_with_the_bare_message() -> None:
    collection = _collection("books")
    _ = collection.add_alias("old", "books").set_deprecated("", "", "Drop %alias_id%.")

    with pytest.warns(DeprecationWarning, match=r"^Drop old\.$"):
        _ = collection.get("old")


def test_an_alias_to_itself_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match='"a" can not reference itself'):
        _ = RouteCollection().add_alias("a", "a")


def test_an_alias_replaces_a_route_under_its_name() -> None:
    collection = _collection("a", "b")

    _ = collection.add_alias("a", "b")

    assert list(collection.all()) == ["b"]
    assert collection.get("a") == _route("/b")


def test_adding_a_route_under_an_alias_name_drops_the_alias() -> None:
    collection = _collection("b")
    _ = collection.add_alias("a", "b")

    collection.add("a", _route("/own"))

    assert collection.get_alias("a") is None
    assert collection.get("a") == _route("/own")


def test_remove_drops_routes_and_the_aliases_left_pointing_at_them() -> None:
    collection = _collection("a", "b")
    _ = collection.add_alias("to_a", "a")
    _ = collection.add_alias("to_b", "b")

    collection.remove("a")

    assert list(collection.all()) == ["b"]
    assert set(collection.get_aliases()) == {"to_b"}


def test_removing_an_alias_leaves_the_aliases_pointing_at_it() -> None:
    collection = _collection("a")
    _ = collection.add_alias("b", "a")
    _ = collection.add_alias("c", "b")

    collection.remove("b")

    assert set(collection.get_aliases()) == {"c"}


def test_add_collection_appends_moving_shared_names_to_the_end() -> None:
    collection = _collection("a", "b")
    other = RouteCollection()
    other.add("a", _route("/other_a"))
    other.add("c", _route("/c"))
    _ = other.add_alias("to_c", "c")

    collection.add_collection(other)

    assert list(collection.all()) == ["b", "a", "c"]
    assert collection.all()["a"].path == "/other_a"
    assert collection.get("to_c") == _route("/c")


def test_add_collection_keeps_the_priorities_it_brings() -> None:
    collection = _collection("a")
    other = RouteCollection()
    other.add("b", _route("/b"), priority=3)

    collection.add_collection(other)

    assert collection.get_priority("b") == 3
    assert list(collection.all()) == ["b", "a"]


def test_an_alias_added_from_another_collection_replaces_a_route_of_that_name() -> None:
    collection = _collection("x", "c")
    other = RouteCollection()
    _ = other.add_alias("x", "c")

    collection.add_collection(other)

    assert list(collection.all()) == ["c"]
    assert collection.get("x") == _route("/c")


@pytest.mark.parametrize("prefix", ["shop", "/shop", "/shop/", " shop "])
def test_add_prefix_puts_every_route_under_the_trimmed_prefix(prefix: str) -> None:
    collection = RouteCollection()
    collection.add("books", _route("/books"))
    collection.add("home", _route("/"))

    collection.add_prefix(prefix)

    assert [route.path for _, route in collection] == ["/shop/books", "/shop/"]


@pytest.mark.parametrize("prefix", ["", "/", "  ", " / "])
def test_a_blank_prefix_changes_nothing(prefix: str) -> None:
    collection = _collection("books")

    collection.add_prefix(prefix)

    assert collection.get("books") == _route("/books")


def test_add_name_prefix_renames_routes_priorities_and_aliases() -> None:
    collection = RouteCollection()
    collection.add("books", _route("/books"), priority=2)
    _ = collection.add_alias("shelf", "books")
    _ = collection.add_alias("outside", "somewhere_else")

    collection.add_name_prefix("shop_")

    assert list(collection.all()) == ["shop_books"]
    assert collection.get_priority("shop_books") == 2
    assert {name: alias.id for name, alias in collection.get_aliases().items()} == {
        "shop_shelf": "shop_books",
        "shop_outside": "somewhere_else",
    }
    assert collection.get("shop_shelf") == _route("/books")


def test_copy_has_its_own_aliases() -> None:
    collection = _collection("books")
    _ = collection.add_alias("old", "books")

    copied = collection.copy()
    alias = copied.get_alias("old")
    assert alias is not None
    _ = alias.set_deprecated("acme/shop", "2.0")

    original = collection.get_alias("old")
    assert original is not None
    assert not original.is_deprecated()
    assert copied.all() == collection.all()
