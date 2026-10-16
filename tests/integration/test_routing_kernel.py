"""What ``setup`` mounts from the route resources and routes files a kernel carries."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from xtr_dependency_injection import Kernel

from xtr_http_kernel import setup
from xtr_http_kernel._route_contexts import route_contexts
from xtr_http_kernel.bundle import ROUTE_REGISTRY_PARAMETER, HttpKernelBundle
from xtr_http_kernel.routing import InvalidArgumentError, RouteConflictError, RouteRegistry

_LOADERS = "tests.fixtures.routing.loaders"
_INCLUDED = "tests.fixtures.routing.included_routes"
_DEFAULT_PATHS = frozenset({"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"})


def _kernel(*resources: str) -> Kernel:
    return Kernel(
        "xtr_http_kernel.bundle",
        env="test",
        bundles={HttpKernelBundle: {"all": True}},
        resources=resources,
    )


def _mounted(app: FastAPI) -> dict[str, str]:
    return {
        view.name: view.path
        for view in route_contexts(app.routes)
        if view.name is not None and view.path is not None and view.path not in _DEFAULT_PATHS
    }


def _paths(*resources: str) -> dict[str, str]:
    app = FastAPI()
    setup(app, _kernel(*resources))
    return _mounted(app)


def test_with_nothing_registered_nothing_is_mounted() -> None:
    assert _paths() == {}


def test_a_resource_no_routes_file_includes_is_not_mounted() -> None:
    assert _paths(_LOADERS) == {}


def test_the_routes_file_including_resources_mounts_them_at_their_own_paths() -> None:
    assert _paths(_LOADERS, _INCLUDED) == {
        "books_list": "/books",
        "books_show": "/books/{book_id}",
        "metadata": "/.well-known/metadata",
    }


def test_a_routes_file_arranges_what_it_includes_and_adds_its_own() -> None:
    assert _paths(_LOADERS, "tests.fixtures.routing.arranged_routes") == {
        "metadata": "/.well-known/metadata",
        "shop_books_list": "/shop/books",
        "shop_books_show": "/shop/books/{book_id}",
        "home": "/",
    }


def test_a_resource_only_one_file_includes_is_the_only_one_mounted() -> None:
    assert _paths(_LOADERS, "tests.fixtures.routing.selective_routes") == {
        "metadata": "/.well-known/metadata",
    }


def test_two_routes_of_one_resource_claiming_one_name_are_refused_while_staging() -> None:
    with pytest.raises(
        InvalidArgumentError, match='Two routes of the resource "books" are named "books_list"'
    ):
        _ = _paths(_LOADERS, "tests.fixtures.routing.duplicate_loaders")


def test_two_resources_contributing_one_name_are_refused_when_both_are_included() -> None:
    with pytest.raises(RouteConflictError, match="two resources contribute the name"):
        _ = _paths(
            _LOADERS,
            "tests.fixtures.routing.clashing_loader",
            "tests.fixtures.routing.conflicting_names_routes",
        )


def test_a_routes_file_asking_for_an_unknown_resource_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="nothing installed contributes"):
        _ = _paths("tests.fixtures.routing.missing_routes")


def test_the_registry_is_stored_under_its_parameter() -> None:
    compiled = _kernel(_LOADERS, _INCLUDED).build()
    registry = compiled.container.get_parameter(ROUTE_REGISTRY_PARAMETER)

    assert isinstance(registry, RouteRegistry)
    assert [resource for resource, _ in registry.resources] == ["books", "well_known"]
    assert len(registry.files) == 1


def test_one_kernel_built_twice_collects_each_build_separately() -> None:
    kernel = _kernel(_LOADERS)

    first = kernel.build().container.get_parameter(ROUTE_REGISTRY_PARAMETER)
    second = kernel.build().container.get_parameter(ROUTE_REGISTRY_PARAMETER)

    assert isinstance(first, RouteRegistry)
    assert isinstance(second, RouteRegistry)
    assert len(first.resources) == len(second.resources) == 2


def test_a_routes_file_under_config_routes_is_found_by_the_application_scan() -> None:
    kernel = Kernel(
        "tests.fixtures.routes_app",
        env="test",
        bundles={HttpKernelBundle: {"all": True}},
        resources=("tests.fixtures.routes_app", _LOADERS),
    )
    app = FastAPI()
    setup(app, kernel)

    assert _mounted(app)["books_list"] == "/shop/books"
