from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from pathlib import PurePosixPath
from typing import cast, final
from uuid import UUID

import pytest

from xtr_http_kernel.data_collector import clone_var


class _Colour(Enum):
    RED = 1


@final
class _Plain:
    def __init__(self) -> None:
        self.title = "Dune"
        self.pages = 412


@final
class _Slotted:
    __slots__ = ("isbn", "unset")

    def __init__(self) -> None:
        self.isbn = "978"

    unset: str  # pyright: ignore[reportUninitializedInstanceVariable] — left unset on purpose: the test reads past it

    @property
    def expensive(self) -> str:
        message = "a property is never read"
        raise AssertionError(message)


@final
class _Node:
    def __init__(self) -> None:
        self.child: object = None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, {"kind": "scalar", "type": "NoneType", "value": None}),
        (True, {"kind": "scalar", "type": "bool", "value": True}),
        (3, {"kind": "scalar", "type": "int", "value": 3}),
        (1.5, {"kind": "scalar", "type": "float", "value": 1.5}),
        (float("inf"), {"kind": "scalar", "type": "float", "value": "inf"}),
        (_Colour.RED, {"kind": "scalar", "type": f"{__name__}._Colour", "value": "_Colour.RED"}),
        (Decimal("1.10"), {"kind": "scalar", "type": "decimal.Decimal", "value": "1.10"}),
        (
            UUID(int=0),
            {
                "kind": "scalar",
                "type": "uuid.UUID",
                "value": "00000000-0000-0000-0000-000000000000",
            },
        ),
        (PurePosixPath("/a"), {"kind": "scalar", "type": "pathlib.PurePosixPath", "value": "/a"}),
        (
            datetime(2026, 1, 1, tzinfo=UTC),
            {"kind": "scalar", "type": "datetime.datetime", "value": "2026-01-01 00:00:00+00:00"},
        ),
    ],
)
def test_a_scalar_is_kept_as_its_value(value: object, expected: dict[str, object]) -> None:
    assert clone_var(value) == expected


def test_a_long_string_is_cut() -> None:
    assert clone_var("abcdef", max_string=4) == {
        "kind": "str",
        "type": "str",
        "value": "abcd",
        "truncated": 2,
    }


def test_bytes_show_their_length_and_first_bytes() -> None:
    cloned = clone_var(b"\x00\x01" * 40)

    assert cloned["length"] == 80
    assert cloned["truncated"] == 16
    assert cloned["value"] == "0001" * 32


def test_a_mapping_keeps_its_pairs_up_to_the_limit() -> None:
    cloned = clone_var({"a": 1, "b": 2, "c": 3}, max_items=2)

    assert cloned["kind"] == "mapping"
    assert cloned["truncated"] == 1
    assert cloned["items"] == [
        [clone_var("a"), clone_var(1)],
        [clone_var("b"), clone_var(2)],
    ]


@pytest.mark.parametrize("value", [[1, 2], (1, 2), {1, 2}, frozenset({1, 2})])
def test_a_sequence_keeps_its_items(value: object) -> None:
    cloned = clone_var(value)

    assert cloned["kind"] == "sequence"
    assert cloned["items"] == [clone_var(1), clone_var(2)]


def test_an_object_shows_its_instance_state() -> None:
    cloned = clone_var(_Plain())

    assert cloned["kind"] == "object"
    assert cloned["type"] == f"{__name__}._Plain"
    assert cloned["attributes"] == [["title", clone_var("Dune")], ["pages", clone_var(412)]]


def test_a_slotted_object_shows_the_slots_it_set_and_never_a_property() -> None:
    cloned = clone_var(_Slotted())

    assert cloned["attributes"] == [["isbn", clone_var("978")]]


def test_an_exception_shows_its_arguments() -> None:
    cloned = clone_var(ValueError("bad"))

    assert ["args", clone_var(("bad",))] in cast("list[object]", cloned["attributes"])


def test_deep_values_are_cut() -> None:
    cloned = clone_var([[[1]]], max_depth=2)

    assert cloned["items"] == [
        {
            "kind": "sequence",
            "type": "list",
            "items": [{"kind": "cut", "type": "list", "reason": "depth"}],
            "truncated": 0,
        }
    ]


def test_a_cycle_is_cut_where_it_closes() -> None:
    node = _Node()
    node.child = node

    cloned = clone_var(node)

    assert cloned["attributes"] == [
        ["child", {"kind": "cut", "type": f"{__name__}._Node", "reason": "recursion"}]
    ]


def test_a_value_met_twice_but_not_in_a_cycle_is_shown_both_times() -> None:
    shared = [1]

    cloned = clone_var([shared, shared])

    assert cloned["items"] == [clone_var([1]), clone_var([1])]


def test_every_tree_is_json() -> None:
    node = _Node()
    node.child = {"when": datetime(2026, 1, 1, tzinfo=UTC), "raw": b"x", "set": {1}}

    cloned = clone_var(node)

    assert json.loads(json.dumps(cloned)) == cloned
