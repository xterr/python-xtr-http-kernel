"""Declaring route resources and routes files.

- :func:`as_route_resource` — a function filling a router for one named resource,
  which a package ships and an application's routes file includes.
- :func:`as_routes` — a function registering what the application serves.
"""

from __future__ import annotations

from .as_route_resource import as_route_resource, route_resources_of
from .as_routes import RoutesFile, as_routes, routes_files_of

__all__ = [
    "RoutesFile",
    "as_route_resource",
    "as_routes",
    "route_resources_of",
    "routes_files_of",
]
