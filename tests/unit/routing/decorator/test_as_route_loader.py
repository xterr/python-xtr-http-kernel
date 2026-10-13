"""``@as_route_loader``: what it records on a class, and what it refuses."""

from __future__ import annotations

import pytest

from xtr_http_kernel.routing import InvalidArgumentError, RouteCollection
from xtr_http_kernel.routing.decorator import RouteLoaderMarker, as_route_loader, route_loaders_of


@as_route_loader("books", prefixable=False)
class _Loader:
    def load_routes(self) -> RouteCollection:
        return RouteCollection()


class _Child(_Loader):
    pass


def test_the_decorated_class_carries_its_resource_and_prefix_rule() -> None:
    assert route_loaders_of(_Loader) == (RouteLoaderMarker("books", prefixable=False),)


def test_a_loader_is_prefixable_unless_told_otherwise() -> None:
    @as_route_loader("shelf")
    class Shelf:
        def load_routes(self) -> RouteCollection:
            return RouteCollection()

    assert route_loaders_of(Shelf) == (RouteLoaderMarker("shelf", prefixable=True),)


def test_a_subclass_does_not_inherit_its_parents_declaration() -> None:
    assert route_loaders_of(_Child) == ()


def test_something_not_a_class_carries_no_declaration() -> None:
    assert route_loaders_of(_Loader()) == ()


def test_a_class_without_load_routes_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="has no load_routes"):

        @as_route_loader("books")
        class _Nothing:
            pass


def test_a_blank_resource_name_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="needs a resource name"):
        _ = as_route_loader("  ")
