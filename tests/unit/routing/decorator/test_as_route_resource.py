"""``@as_route_resource``: what it records on a function, and what it refuses."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from xtr_http_kernel.routing import InvalidArgumentError
from xtr_http_kernel.routing.decorator import as_route_resource, route_resources_of
from xtr_http_kernel.routing.decorator.as_route_resource import ROUTE_RESOURCE_ATTRIBUTE

if TYPE_CHECKING:
    from fastapi import APIRouter


def test_the_decorated_function_carries_its_resource_name() -> None:
    @as_route_resource("webhook")
    def webhook_routes(router: APIRouter) -> None:
        """Fill."""
        del router

    assert webhook_routes.__dict__[ROUTE_RESOURCE_ATTRIBUTE] == "webhook"
    assert route_resources_of(webhook_routes) == ("webhook",)


def test_a_blank_resource_name_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="needs a name"):
        _ = as_route_resource("  ")


def test_a_target_that_is_no_plain_function_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="plain function"):
        _ = as_route_resource("books")(42)

    with pytest.raises(InvalidArgumentError, match="plain function"):

        @as_route_resource("books")
        class Books:
            """Not a function."""


def test_a_coroutine_function_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="plain function"):

        @as_route_resource("books")
        async def books_routes(router: APIRouter) -> None:
            """Fill, asynchronously — which setup would never await."""
            del router


def test_anything_undeclared_carries_no_resource() -> None:
    def plain(router: APIRouter) -> None:
        """Carry no declaration."""
        del router

    assert route_resources_of(plain) == ()
    assert route_resources_of(42) == ()
    assert route_resources_of(cast("object", dict)) == ()
