"""The registry pass: what it stores, collected from the scan."""

from __future__ import annotations

from xtr_dependency_injection import Kernel

from xtr_http_kernel.bundle import ROUTE_REGISTRY_PARAMETER, HttpKernelBundle
from xtr_http_kernel.routing import RouteRegistry


def _registry(*resources: str) -> RouteRegistry:
    kernel = Kernel(
        "xtr_http_kernel.bundle",
        env="test",
        bundles={HttpKernelBundle: {"all": True}},
        resources=resources,
    )
    registry = kernel.build().container.get_parameter(ROUTE_REGISTRY_PARAMETER)
    assert isinstance(registry, RouteRegistry)
    return registry


def test_the_registry_is_stored_under_its_parameter() -> None:
    registry = _registry("tests.fixtures.routing.loaders")

    assert [resource for resource, _ in registry.resources] == ["books", "well_known"]
    assert registry.files == ()


def test_routes_files_are_collected_beside_the_resources() -> None:
    registry = _registry("tests.fixtures.routing.loaders", "tests.fixtures.routing.included_routes")

    assert len(registry.resources) == 2
    assert len(registry.files) == 1


def test_with_nothing_scanned_the_registry_is_empty() -> None:
    registry = _registry()

    assert registry.resources == ()
    assert registry.files == ()
