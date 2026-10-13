"""Declaring another name for a route in a routes file."""

from __future__ import annotations

import pytest

from tests.unit.routing.loader.configurator.support import books
from xtr_http_kernel.routing import InvalidArgumentError
from xtr_http_kernel.routing.loader.configurator import AliasConfigurator


def test_an_alias_is_added_to_the_table() -> None:
    collection = books()

    AliasConfigurator("catalogue", "list").apply_to(collection)

    assert collection.get("catalogue") == collection.get("list")


def test_a_deprecated_alias_is_added_deprecated() -> None:
    collection = books()

    AliasConfigurator("old", "list").deprecate("acme/shop", "2.0").apply_to(collection)

    alias = collection.get_alias("old")
    assert alias is not None
    assert alias.is_deprecated()


def test_a_bad_deprecation_message_is_refused_where_it_is_written() -> None:
    with pytest.raises(InvalidArgumentError, match="%alias_id%"):
        _ = AliasConfigurator("old", "list").deprecate("acme/shop", "2.0", "Stop.")
