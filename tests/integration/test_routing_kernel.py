"""The route table a kernel builds from route loaders and routes files while it compiles."""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel

from xtr_http_kernel.bundle import ROUTE_TABLE_PARAMETER, HttpKernelBundle
from xtr_http_kernel.routing import InvalidArgumentError, RouteCollection, RouterInterface

pytestmark = pytest.mark.anyio

_LOADERS = "tests.fixtures.routing.loaders"


def _kernel(*resources: str) -> Kernel:
    return Kernel(
        "xtr_http_kernel.bundle",
        env="test",
        bundles={HttpKernelBundle: {"all": True}},
        resources=resources,
    )


def _paths(*resources: str) -> dict[str, str]:
    table = _kernel(*resources).build().container.get_parameter(ROUTE_TABLE_PARAMETER)
    assert isinstance(table, RouteCollection)
    return {name: route.path for name, route in table}


def test_with_nothing_registered_the_table_is_empty() -> None:
    assert _paths() == {}


def test_a_resource_no_routes_file_mentions_is_served_at_its_own_paths() -> None:
    assert _paths(_LOADERS) == {
        "books_list": "/books",
        "books_show": "/books/{book_id}",
        "metadata": "/.well-known/metadata",
    }


def test_a_routes_file_arranges_what_it_imports_and_adds_its_own() -> None:
    assert _paths(_LOADERS, "tests.fixtures.routing.arranged_routes") == {
        "metadata": "/.well-known/metadata",
        "shop_books_list": "/shop/books",
        "home": "/",
    }


def test_a_skipped_resource_is_not_served() -> None:
    assert _paths(_LOADERS, "tests.fixtures.routing.skipping_routes") == {
        "metadata": "/.well-known/metadata",
    }


def test_moving_routes_a_standard_fixes_is_refused_while_compiling() -> None:
    with pytest.raises(InvalidArgumentError, match='"well_known" are at a place a standard fixes'):
        _ = _kernel(_LOADERS, "tests.fixtures.routing.fixed_prefix_routes").build()


def test_two_loaders_claiming_one_resource_are_refused_while_compiling() -> None:
    with pytest.raises(
        InvalidArgumentError, match='Two route loaders provide the resource "books"'
    ):
        _ = _kernel(_LOADERS, "tests.fixtures.routing.duplicate_loaders").build()


def test_a_loader_asking_for_arguments_is_refused_while_compiling() -> None:
    with pytest.raises(InvalidArgumentError, match="cannot be built with no arguments"):
        _ = _kernel("tests.fixtures.routing.needs_arguments_loader").build()


def test_a_loader_whose_load_routes_is_a_coroutine_is_refused_while_compiling() -> None:
    with pytest.raises(InvalidArgumentError, match=r"defines load_routes\(\) as a coroutine"):
        _ = _kernel("tests.fixtures.routing.async_loader").build()


def test_a_routes_file_written_as_a_coroutine_is_refused_while_compiling() -> None:
    with pytest.raises(InvalidArgumentError, match="is a coroutine function"):
        _ = _kernel(_LOADERS, "tests.fixtures.routing.async_routes").build()


def test_two_resources_contributing_one_route_name_are_refused_while_compiling() -> None:
    with pytest.raises(InvalidArgumentError, match=r'"books" and "library" both contribute'):
        _ = _kernel(_LOADERS, "tests.fixtures.routing.clashing_loader").build()


def test_a_resource_skipped_by_one_file_and_imported_by_another_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="skipped by one routes file and imported"):
        _ = _kernel(
            _LOADERS,
            "tests.fixtures.routing.arranged_routes",
            "tests.fixtures.routing.skipping_routes",
        ).build()


async def test_the_router_service_holds_the_table_built_while_compiling() -> None:
    compiled = _kernel(_LOADERS).build()
    table = compiled.container.get_parameter(ROUTE_TABLE_PARAMETER)

    async with await compiled.boot() as booted:
        router = await booted.container.get(RouterInterface)

    assert isinstance(table, RouteCollection)
    assert router.get_route_collection().all() == table.all()


def test_a_routes_file_under_config_routes_is_found_by_the_application_scan() -> None:
    kernel = Kernel(
        "tests.fixtures.routes_app",
        env="test",
        bundles={HttpKernelBundle: {"all": True}},
        resources=("tests.fixtures.routes_app", _LOADERS),
    )

    table = kernel.build().container.get_parameter(ROUTE_TABLE_PARAMETER)

    assert isinstance(table, RouteCollection)
    assert {name: route.path for name, route in table}["books_list"] == "/shop/books"
