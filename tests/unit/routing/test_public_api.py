"""What ``xtr_http_kernel.routing`` exports."""

from __future__ import annotations

from xtr_http_kernel import routing
from xtr_http_kernel.exception import HttpKernelError


def test_every_exported_name_exists() -> None:
    assert all(hasattr(routing, name) for name in routing.__all__)


def test_every_routing_error_is_exported_and_derives_from_the_routing_base() -> None:
    exported = {name for name in routing.__all__ if name.endswith("Error")}

    assert exported == {
        "InvalidArgumentError",
        "RouteConflictError",
        "RoutingError",
    }
    assert issubclass(routing.InvalidArgumentError, routing.RoutingError)
    assert issubclass(routing.RouteConflictError, routing.RoutingError)


def test_the_routing_base_is_one_of_the_librarys_errors() -> None:
    assert issubclass(routing.RoutingError, HttpKernelError)


def test_the_registry_and_its_parameter_are_exported() -> None:
    assert routing.ROUTE_REGISTRY_PARAMETER == "http_kernel.route_registry"
    assert routing.RouteRegistry().resources == ()
