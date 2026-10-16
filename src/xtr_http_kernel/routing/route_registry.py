"""What the scan found for routing: the resources and the routes files."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import APIRouter

    from xtr_http_kernel.routing.decorator.as_routes import RoutesFile

__all__ = ["ROUTE_REGISTRY_PARAMETER", "RouteRegistry"]

ROUTE_REGISTRY_PARAMETER: Final = "http_kernel.route_registry"
"""The parameter the registry is stored under while the kernel compiles."""


@final
@dataclass(frozen=True, slots=True)
class RouteRegistry:
    """Everything routing discovered, carried from the scan to ``setup``.

    Attributes:
        resources: Each contributing function with the resource it fills, in
            scan order — several functions may fill one resource.
        files: The application's routes files, in scan order. ``setup`` runs
            them, and only what they include is served.
    """

    resources: tuple[tuple[str, Callable[[APIRouter], None]], ...] = ()
    files: tuple[RoutesFile, ...] = ()
