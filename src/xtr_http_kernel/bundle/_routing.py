"""The ``Router`` service, holding the table the routing pass built."""

from __future__ import annotations

from typing import Annotated

# Read at runtime: the container fills the factory's parameter from these.
from xtr_dependency_injection import Autowire

from xtr_http_kernel.routing.route_collection import (  # noqa: TC001 — read at runtime, as above
    RouteCollection,
)
from xtr_http_kernel.routing.router import Router

from .routing_resolver_pass import ROUTE_TABLE_PARAMETER

__all__ = ["router"]


def router(table: Annotated[RouteCollection, Autowire(param=ROUTE_TABLE_PARAMETER)]) -> Router:
    """Hold the route table the routing pass built while the kernel compiled."""
    return Router(table)
