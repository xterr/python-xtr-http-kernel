"""The marker ``@as_route_loader`` leaves on a class."""

from __future__ import annotations

from xtr_http_kernel.routing.decorator import RouteLoaderMarker


def test_a_marker_is_prefixable_by_default() -> None:
    assert RouteLoaderMarker("books").prefixable
