"""One route: its normalised path and methods, and the options it passes on."""

from __future__ import annotations

import pytest
from fastapi.datastructures import DefaultPlaceholder

from xtr_http_kernel.routing import Route


async def _endpoint() -> dict[str, str]:
    return {}


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("books", "/books"),
        ("/books", "/books"),
        ("//books", "/books"),
        ("  books ", "/books"),
        ("", "/"),
    ],
)
def test_the_path_always_has_one_leading_slash(given: str, expected: str) -> None:
    assert Route(given, _endpoint).path == expected


def test_methods_are_upper_cased_and_kept_once_in_order() -> None:
    route = Route("/", _endpoint, methods=("post", "GET", "get", "Post"))

    assert route.methods == ("POST", "GET")


def test_a_response_model_left_unnamed_is_the_frameworks_own_marker() -> None:
    assert isinstance(Route("/", _endpoint).response_model, DefaultPlaceholder)


def test_an_explicit_none_response_model_is_kept() -> None:
    assert Route("/", _endpoint, response_model=None).response_model is None


def test_with_path_returns_a_route_at_the_new_path_and_leaves_the_original() -> None:
    route = Route("/books", _endpoint, methods=("GET",), tags=("shelf",))

    moved = route.with_path("shop/books")

    assert moved.path == "/shop/books"
    assert (moved.methods, moved.tags, moved.endpoint) == (("GET",), ("shelf",), _endpoint)
    assert route.path == "/books"


def test_two_routes_with_the_same_settings_are_equal_and_hash_alike() -> None:
    first = Route("/books", _endpoint, methods=("GET",))
    second = Route("books", _endpoint, methods=("get",))

    assert first == second
    assert hash(first) == hash(second)
