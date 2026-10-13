"""What a routes file receives: the application's whole route table to arrange."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_http_kernel.routing.exception.invalid_argument_error import InvalidArgumentError

from .alias_configurator import AliasConfigurator
from .collection_configurator import CollectionConfigurator
from .import_configurator import ImportConfigurator
from .route_configurator import RouteConfigurator

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_kernel.routing.route_collection import RouteCollection

    from ._step_interface import StepInterface

__all__ = ["RoutingConfigurator"]


@final
class RoutingConfigurator:
    """What a routes file receives: imports, routes, groups and aliases, in its order.

    Nothing reaches the table while the file runs. Every call is recorded and
    the whole file is applied when it returns, in the order it was written — so
    a route defined after an import replaces the imported route of that name.

    A resource no routes file imports or skips is still served, at its own
    paths and names; importing or skipping it is what hands it to a file.
    """

    __slots__ = ("_fixed", "_imported", "_resources", "_skipped", "_steps")

    _resources: Mapping[str, RouteCollection]
    _fixed: frozenset[str]
    _imported: set[str]
    _skipped: set[str]
    _steps: list[StepInterface]

    def __init__(self, resources: Mapping[str, RouteCollection], fixed: frozenset[str]) -> None:
        """Offer the routes every loader returned, by resource name.

        Args:
            resources: Each resource's routes, as its loader returned them.
            fixed: The resources whose routes a standard puts at a fixed place.
        """
        self._resources = resources
        self._fixed = fixed
        self._imported = set()
        self._skipped = set()
        self._steps = []

    @property
    def mentioned(self) -> frozenset[str]:
        """The resources this file imported or skipped."""
        return frozenset(self._imported | self._skipped)

    @property
    def imported(self) -> frozenset[str]:
        """The resources this file imported."""
        return frozenset(self._imported)

    @property
    def skipped(self) -> frozenset[str]:
        """The resources this file skipped."""
        return frozenset(self._skipped)

    def import_(self, resource: str) -> ImportConfigurator:
        """Import a resource's routes; arrange them with what is returned.

        Raises:
            InvalidArgumentError: No loader provides the resource.
        """
        routes = self._resource(resource)
        self._imported.add(resource)
        imported = ImportConfigurator(resource, routes, prefixable=resource not in self._fixed)
        self._steps.append(imported)
        return imported

    def skip(self, resource: str) -> None:
        """Serve none of a resource's routes.

        Raises:
            InvalidArgumentError: No loader provides the resource.
        """
        _ = self._resource(resource)
        self._skipped.add(resource)

    def add(self, name: str, path: str) -> RouteConfigurator:
        """Define a route, or redefine one of an imported resource by its name."""
        route = RouteConfigurator(name, path)
        self._steps.append(route)
        return route

    def alias(self, name: str, target: str) -> AliasConfigurator:
        """Make ``name`` another name for the route ``target``."""
        alias = AliasConfigurator(name, target)
        self._steps.append(alias)
        return alias

    def collection(self, name_prefix: str = "") -> CollectionConfigurator:
        """Start a group of routes sharing a path prefix and a name prefix."""
        group = CollectionConfigurator(name_prefix)
        self._steps.append(group)
        return group

    def apply(self, collection: RouteCollection) -> None:
        """Apply everything the file asked for to ``collection``, in its order."""
        for step in self._steps:
            step.apply_to(collection)

    def _resource(self, resource: str) -> RouteCollection:
        routes = self._resources.get(resource)
        if routes is None:
            known = ", ".join(map(repr, sorted(self._resources))) or "none"
            raise InvalidArgumentError(
                f'No route loader provides the resource "{resource}"; the known ones are {known}.'
            )
        return routes
