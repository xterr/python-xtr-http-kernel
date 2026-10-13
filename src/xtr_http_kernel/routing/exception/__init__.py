"""The errors the route table raises, one family under one base.

- :class:`RoutingError` — the base of them all, itself an ``HttpKernelError``.
- :class:`InvalidArgumentError` — a value the table cannot work with.
- :class:`RouteCircularReferenceError` — aliases that loop back on themselves.
- :class:`RouteConflictError` — a mounted route colliding with the application's own.
"""

from __future__ import annotations

from .invalid_argument_error import InvalidArgumentError
from .route_circular_reference_error import RouteCircularReferenceError
from .route_conflict_error import RouteConflictError
from .routing_error import RoutingError

__all__ = [
    "InvalidArgumentError",
    "RouteCircularReferenceError",
    "RouteConflictError",
    "RoutingError",
]
