"""The routing pass: the table it stores, built from the loaders and routes files it was given."""

from __future__ import annotations

from xtr_dependency_injection import Kernel

from xtr_http_kernel.bundle import ROUTE_TABLE_PARAMETER, HttpKernelBundle
from xtr_http_kernel.routing import RouteCollection


def _table(*resources: str) -> list[str]:
    kernel = Kernel(
        "xtr_http_kernel.bundle",
        env="test",
        bundles={HttpKernelBundle: {"all": True}},
        resources=resources,
    )
    table = kernel.build().container.get_parameter(ROUTE_TABLE_PARAMETER)
    assert isinstance(table, RouteCollection)
    return list(table.all())


def test_the_table_is_stored_under_the_route_table_parameter() -> None:
    assert _table("tests.fixtures.routing.loaders") == ["books_list", "books_show", "metadata"]


def test_with_no_loader_the_stored_table_is_empty() -> None:
    assert _table() == []
