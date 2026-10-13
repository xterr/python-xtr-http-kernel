"""The route table: named routes bundles contribute and applications arrange.

Routes are only arranged here — added, renamed, prefixed, left out, aliased.
Matching a request and building a URL stay with the web framework, which every
route reaches under its name.
"""

from __future__ import annotations

from .alias import Alias
from .alias_deprecation import AliasDeprecation
from .exception import (
    InvalidArgumentError,
    RouteCircularReferenceError,
    RouteConflictError,
    RoutingError,
)
from .route import Route
from .route_collection import RouteCollection
from .route_loader_interface import RouteLoaderInterface
from .router import Router
from .router_interface import RouterInterface

__all__ = [
    "Alias",
    "AliasDeprecation",
    "InvalidArgumentError",
    "Route",
    "RouteCircularReferenceError",
    "RouteCollection",
    "RouteConflictError",
    "RouteLoaderInterface",
    "Router",
    "RouterInterface",
    "RoutingError",
]
