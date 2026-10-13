"""``@as_routes``: which functions are routes files."""

from __future__ import annotations

from xtr_http_kernel.routing.decorator import as_routes, routes_files_of
from xtr_http_kernel.routing.loader.configurator import RoutingConfigurator


@as_routes
def _declared(routes: RoutingConfigurator) -> None:
    del routes


def _plain(routes: RoutingConfigurator) -> None:
    del routes


def test_a_declared_function_is_a_routes_file() -> None:
    assert routes_files_of(_declared) == (_declared,)


def test_an_undeclared_function_is_not() -> None:
    assert routes_files_of(_plain) == ()


def test_a_class_or_a_value_is_not() -> None:
    assert routes_files_of(RoutingConfigurator) == ()
    assert routes_files_of("routes") == ()
