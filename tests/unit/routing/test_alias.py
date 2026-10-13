"""Another name for a route, and its deprecation."""

from __future__ import annotations

import pytest

from xtr_http_kernel.routing import Alias, InvalidArgumentError


def test_an_alias_stands_for_its_target() -> None:
    assert Alias("books").id == "books"


def test_with_id_returns_a_copy_standing_for_another_name_and_keeping_the_deprecation() -> None:
    alias = Alias("books").set_deprecated("acme/shop", "2.0")

    other = alias.with_id("shop_books")

    assert (other.id, other.is_deprecated()) == ("shop_books", True)
    assert alias.id == "books"


def test_a_new_alias_is_not_deprecated() -> None:
    alias = Alias("books")

    assert not alias.is_deprecated()
    assert alias.get_deprecation("old_books") is None


def test_the_deprecation_names_the_alias_where_the_message_asks_for_it() -> None:
    alias = Alias("books").set_deprecated("acme/shop", "2.0", 'Use "books", not "%alias_id%".')

    assert alias.get_deprecation("old_books") == {
        "package": "acme/shop",
        "version": "2.0",
        "message": 'Use "books", not "old_books".',
    }


def test_an_empty_message_uses_the_standard_one() -> None:
    deprecation = Alias("books").set_deprecated("acme/shop", "2.0").get_deprecation("old_books")

    assert deprecation is not None
    assert deprecation["message"].startswith('The "old_books" route alias is deprecated.')


@pytest.mark.parametrize(
    "message", ["line\none %alias_id%", "line\rone %alias_id%", "end */ %alias_id%"]
)
def test_a_message_with_forbidden_characters_is_refused(message: str) -> None:
    with pytest.raises(InvalidArgumentError, match="Invalid characters"):
        _ = Alias("books").set_deprecated("acme/shop", "2.0", message)


def test_a_message_not_naming_the_alias_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="%alias_id%"):
        _ = Alias("books").set_deprecated("acme/shop", "2.0", "Stop using it.")
