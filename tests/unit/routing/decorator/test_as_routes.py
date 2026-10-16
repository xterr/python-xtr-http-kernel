"""``@as_routes``: what it records on a function, and what it refuses."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_http_kernel.routing import InvalidArgumentError
from xtr_http_kernel.routing.decorator import as_routes, routes_files_of
from xtr_http_kernel.routing.decorator.as_routes import ROUTES_ATTRIBUTE

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import APIRouter, FastAPI


def test_the_decorated_function_is_the_one_the_reader_finds() -> None:
    def _arrange(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
        """Include everything — a stand-in routes file."""
        del app, resources

    declared = as_routes(_arrange)

    assert declared.__dict__[ROUTES_ATTRIBUTE] is True
    assert routes_files_of(declared) == (declared,)


def test_anything_undeclared_is_no_routes_file() -> None:
    def _arrange(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
        """Stay undeclared."""
        del app, resources

    assert routes_files_of(_arrange) == ()
    assert routes_files_of(42) == ()
    assert routes_files_of(type) == ()


def test_a_coroutine_function_is_refused_where_it_is_declared() -> None:
    with pytest.raises(InvalidArgumentError, match="plain function"):

        @as_routes  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        async def arranged(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
            """Arrange — asynchronously, which setup would never await."""
            del app, resources


def test_a_target_that_is_no_function_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="plain function"):
        _ = as_routes(42)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
