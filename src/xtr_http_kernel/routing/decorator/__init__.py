"""Declaring route loaders and routes files.

- :func:`as_route_loader` — a class whose ``load_routes()`` contributes a named set of routes.
- :func:`as_routes` — a function arranging the application's routes.
"""

from __future__ import annotations

from .as_route_loader import as_route_loader, route_loaders_of
from .as_routes import RoutesFile, as_routes, routes_files_of
from .route_loader_marker import RouteLoaderMarker

__all__ = [
    "RouteLoaderMarker",
    "RoutesFile",
    "as_route_loader",
    "as_routes",
    "route_loaders_of",
    "routes_files_of",
]
