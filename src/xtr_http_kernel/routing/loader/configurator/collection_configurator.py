"""Grouping routes of a routes file under one path and name prefix."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

from xtr_http_kernel.routing.route_collection import RouteCollection

from .alias_configurator import AliasConfigurator
from .route_configurator import RouteConfigurator

if TYPE_CHECKING:
    from ._step_interface import StepInterface

__all__ = ["CollectionConfigurator"]


@final
class CollectionConfigurator:
    """Routes defined together, under one path prefix and one name prefix.

    Each route of the group needs its own endpoint: the group starts empty, so
    there is no earlier route of the same name to take one from.
    """

    __slots__ = ("_name_prefix", "_prefix", "_steps")

    _name_prefix: str
    _prefix: str
    _steps: list[StepInterface]

    def __init__(self, name_prefix: str = "") -> None:
        """Start a group whose route names all begin with ``name_prefix``."""
        self._name_prefix = name_prefix
        self._prefix = ""
        self._steps = []

    def prefix(self, prefix: str) -> Self:
        """Put every route of the group under a path prefix."""
        self._prefix = prefix
        return self

    def add(self, name: str, path: str) -> RouteConfigurator:
        """Define a route of the group."""
        route = RouteConfigurator(name, path)
        self._steps.append(route)
        return route

    def alias(self, name: str, target: str) -> AliasConfigurator:
        """Make ``name`` another name for ``target``, both within the group."""
        alias = AliasConfigurator(name, target)
        self._steps.append(alias)
        return alias

    def collection(self, name_prefix: str = "") -> CollectionConfigurator:
        """Start a group inside this one."""
        group = CollectionConfigurator(name_prefix)
        self._steps.append(group)
        return group

    def apply_to(self, collection: RouteCollection) -> None:
        """Build the group and add it to ``collection``."""
        group = RouteCollection()
        for step in self._steps:
            step.apply_to(group)
        group.add_prefix(self._prefix)
        if self._name_prefix:
            group.add_name_prefix(self._name_prefix)
        collection.add_collection(group)
