"""The routing layer: what packages contribute, and what the application registers.

Routing is never imported automatically. A package declares route resources —
:func:`~xtr_http_kernel.routing.decorator.as_route_resource` functions filling
an ``APIRouter`` with native framework routes — and the application's routes
files include them, with the framework's own ``include_router``, while
``setup`` mounts the application. This package holds what the scan carries
between the two — the registry — and the errors the mount refuses with.
"""

from __future__ import annotations

from .exception import InvalidArgumentError, RouteConflictError, RoutingError
from .route_registry import ROUTE_REGISTRY_PARAMETER, RouteRegistry

__all__ = [
    "ROUTE_REGISTRY_PARAMETER",
    "InvalidArgumentError",
    "RouteConflictError",
    "RouteRegistry",
    "RoutingError",
]
