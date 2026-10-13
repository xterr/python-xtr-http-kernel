"""An ordered, name-keyed set of routes and the aliases pointing at them."""

from __future__ import annotations

import copy
import warnings
from typing import TYPE_CHECKING, final

from .alias import Alias
from .exception.invalid_argument_error import InvalidArgumentError
from .exception.route_circular_reference_error import RouteCircularReferenceError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .route import Route

__all__ = ["RouteCollection"]


@final
class RouteCollection:
    """An ordered, name-keyed set of routes and the aliases pointing at them.

    Order is declaration order: adding a name again replaces its route and
    moves it to the end, so the last definition of a name wins and sits where
    it was last declared. A priority moves a route ahead of the ones declared
    before it; equal priorities keep declaration order.
    """

    __slots__ = ("_aliases", "_priorities", "_routes")

    _routes: dict[str, Route]
    _aliases: dict[str, Alias]
    _priorities: dict[str, int]

    def __init__(self) -> None:
        """Start empty."""
        self._routes = {}
        self._aliases = {}
        self._priorities = {}

    def __iter__(self) -> Iterator[tuple[str, Route]]:
        """Yield each name and its route, in the order :meth:`all` gives."""
        return iter(self.all().items())

    def __len__(self) -> int:
        """Count the routes, aliases left out."""
        return len(self._routes)

    def add(self, name: str, route: Route, priority: int = 0) -> None:
        """Add a route under a name, replacing whatever the name held and moving it to the end."""
        self._unset(name)
        self._routes[name] = route
        if priority:
            self._priorities[name] = priority

    def all(self) -> dict[str, Route]:
        """Return every route by name, higher priority first, then in declaration order."""
        if not self._priorities:
            return dict(self._routes)
        order = {name: index for index, name in enumerate(self._routes)}
        names = sorted(self._routes, key=lambda name: (-self._priorities.get(name, 0), order[name]))
        return {name: self._routes[name] for name in names}

    def get(self, name: str) -> Route | None:
        """Return the route under a name, following aliases, or ``None``.

        Raises:
            RouteCircularReferenceError: The aliases loop back on themselves.
        """
        visited: list[str] = []
        current = name
        while (alias := self._aliases.get(current)) is not None:
            if current in visited:
                start = visited.index(current)
                raise RouteCircularReferenceError(current, [*visited[start:], current])
            deprecation = alias.get_deprecation(current)
            if deprecation is not None:
                prefix = " ".join(
                    part for part in (deprecation["package"], deprecation["version"]) if part
                )
                text = (
                    f"Since {prefix}: {deprecation['message']}"
                    if prefix
                    else deprecation["message"]
                )
                warnings.warn(text, DeprecationWarning, stacklevel=2)
            visited.append(current)
            current = alias.id
        return self._routes.get(current)

    def remove(self, *names: str) -> None:
        """Remove routes or aliases by name, and the aliases left pointing at a removed route."""
        removed = {name for name in names if name in self._routes}
        for name in names:
            self._unset(name)
        if removed:
            self._aliases = {
                key: alias for key, alias in self._aliases.items() if alias.id not in removed
            }

    def add_collection(self, collection: RouteCollection) -> None:
        """Append another collection's routes and aliases, each moved to the end."""
        for name, route in collection._routes.items():
            self.add(name, route, collection.get_priority(name) or 0)
        for name, alias in collection._aliases.items():
            self._unset(name)
            self._aliases[name] = alias

    def add_prefix(self, prefix: str) -> None:
        """Put every route under a path prefix; a blank prefix changes nothing."""
        trimmed = prefix.strip().strip("/")
        if not trimmed:
            return
        self._routes = {
            name: route.with_path(f"/{trimmed}{route.path}") for name, route in self._routes.items()
        }

    def add_name_prefix(self, prefix: str) -> None:
        """Prefix every route and alias name, and alias targets that are in this collection."""
        own = self._routes.keys() | self._aliases.keys()
        self._routes = {f"{prefix}{name}": route for name, route in self._routes.items()}
        self._priorities = {
            f"{prefix}{name}": priority for name, priority in self._priorities.items()
        }
        self._aliases = {
            f"{prefix}{name}": alias.with_id(f"{prefix}{alias.id}" if alias.id in own else alias.id)
            for name, alias in self._aliases.items()
        }

    def add_alias(self, name: str, alias: str) -> Alias:
        """Make ``name`` another name for ``alias`` and return the stored alias.

        Raises:
            InvalidArgumentError: ``name`` and ``alias`` are the same.
        """
        if name == alias:
            raise InvalidArgumentError(f'Route alias "{name}" can not reference itself.')
        _ = self._routes.pop(name, None)
        _ = self._priorities.pop(name, None)
        stored = Alias(alias)
        self._aliases[name] = stored
        return stored

    def get_aliases(self) -> dict[str, Alias]:
        """Return every alias by name."""
        return dict(self._aliases)

    def get_alias(self, name: str) -> Alias | None:
        """Return the alias under a name, or ``None``."""
        return self._aliases.get(name)

    def get_priority(self, name: str) -> int | None:
        """Return a route's priority, or ``None`` when it has none."""
        return self._priorities.get(name)

    def copy(self) -> RouteCollection:
        """Return a copy whose aliases can be changed without touching this one's."""
        other = RouteCollection()
        other._routes = dict(self._routes)
        other._priorities = dict(self._priorities)
        other._aliases = {name: copy.copy(alias) for name, alias in self._aliases.items()}
        return other

    def _unset(self, name: str) -> None:
        _ = self._routes.pop(name, None)
        _ = self._priorities.pop(name, None)
        _ = self._aliases.pop(name, None)
