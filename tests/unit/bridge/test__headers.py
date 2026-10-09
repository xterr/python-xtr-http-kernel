"""Headers either side of the bridge: a message's, and the wire's."""

from __future__ import annotations

import pytest
from xtr_http_message import Response
from xtr_http_message.exception import InvalidArgumentError

from xtr_http_kernel.bridge._headers import grouped_headers, raw_headers, with_raw_headers


def test_a_messages_headers_go_to_the_wire_lowercased_one_pair_per_value() -> None:
    message = Response(200, {"X-Books": ["one", "two"], "X-Shelf": "7"})

    assert raw_headers(message) == [
        (b"x-books", b"one"),
        (b"x-books", b"two"),
        (b"x-shelf", b"7"),
    ]


def test_a_message_with_no_header_goes_to_the_wire_with_none() -> None:
    assert raw_headers(Response()) == []


def test_the_wires_pairs_group_under_one_name_each() -> None:
    assert grouped_headers([(b"x-books", b"one"), (b"x-shelf", b"7")]) == {
        "x-books": ["one"],
        "x-shelf": ["7"],
    }


def test_a_name_sent_twice_keeps_both_values_under_the_case_it_first_arrived_in() -> None:
    assert grouped_headers([(b"X-Books", b"one"), (b"x-books", b"two")]) == {
        "X-Books": ["one", "two"]
    }


def test_the_wires_pairs_become_the_only_headers_the_message_carries() -> None:
    message = Response(200, {"X-Books": "one"})

    replaced = with_raw_headers(message, [(b"x-shelf", b"7")])

    assert (replaced.has_header("x-books"), replaced.get_header("x-shelf")) == (False, ["7"])


def test_replacing_the_headers_leaves_the_message_it_was_asked_of_alone() -> None:
    message = Response(200, {"X-Books": "one"})

    _ = with_raw_headers(message, [])

    assert message.get_header("x-books") == ["one"]


def test_replacing_the_headers_keeps_every_value_of_a_repeated_name() -> None:
    replaced = with_raw_headers(Response(), [(b"x-books", b"one"), (b"x-books", b"two")])

    assert replaced.get_header("x-books") == ["one", "two"]


def test_a_pair_that_is_not_a_header_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = with_raw_headers(Response(), [(b" x-broken", b"one")])
