"""What a routes file arranges the route table with."""

from __future__ import annotations

from .alias_configurator import AliasConfigurator
from .collection_configurator import CollectionConfigurator
from .import_configurator import ImportConfigurator
from .route_configurator import RouteConfigurator
from .routing_configurator import RoutingConfigurator

__all__ = [
    "AliasConfigurator",
    "CollectionConfigurator",
    "ImportConfigurator",
    "RouteConfigurator",
    "RoutingConfigurator",
]
