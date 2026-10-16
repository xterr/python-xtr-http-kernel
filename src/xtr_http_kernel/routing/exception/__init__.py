"""The errors the routing layer raises, one family under one base.

- :class:`RoutingError` — the base of them all, itself an ``HttpKernelError``.
- :class:`InvalidArgumentError` — a value routing cannot work with.
- :class:`RouteConflictError` — a mounted route colliding with the application's own.
"""

from __future__ import annotations

from .invalid_argument_error import InvalidArgumentError
from .route_conflict_error import RouteConflictError
from .routing_error import RoutingError

__all__ = ["InvalidArgumentError", "RouteConflictError", "RoutingError"]
