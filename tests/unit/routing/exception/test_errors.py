"""The route table's errors: what each carries, and what else it is caught as."""

from __future__ import annotations

from xtr_http_kernel import InvalidArgumentError as KernelInvalidArgumentError
from xtr_http_kernel.routing.exception import (
    InvalidArgumentError,
    RouteCircularReferenceError,
    RouteConflictError,
)


def test_an_invalid_argument_carries_its_reason_and_is_a_value_error() -> None:
    error = InvalidArgumentError("bad")

    assert (error.reason, str(error)) == ("bad", "bad")
    assert isinstance(error, ValueError)


def test_an_invalid_argument_is_caught_as_the_librarys_own() -> None:
    assert isinstance(InvalidArgumentError("bad"), KernelInvalidArgumentError)


def test_a_circular_reference_keeps_the_path_it_went_through() -> None:
    error = RouteCircularReferenceError("a", ["a", "b", "a"])

    assert error.path == ("a", "b", "a")


def test_a_conflict_names_both_routes_and_why() -> None:
    error = RouteConflictError("books_list", "/books", "my_books", "they share the name")

    assert (error.name, error.path, error.declared, error.reason) == (
        "books_list",
        "/books",
        "my_books",
        "they share the name",
    )
    assert '"my_books"' in str(error)
