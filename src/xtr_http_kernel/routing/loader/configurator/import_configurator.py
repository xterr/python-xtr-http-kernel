"""Bringing a route loader's routes into the application's table."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

from xtr_http_kernel.routing.exception.invalid_argument_error import InvalidArgumentError

if TYPE_CHECKING:
    from xtr_http_kernel.routing.route_collection import RouteCollection

__all__ = ["ImportConfigurator"]


@final
class ImportConfigurator:
    """Imports a resource's routes, applied when the routes file returns.

    Each call refuses a mistake where it is written: a prefix on routes a
    standard fixes, or leaving out a route the resource does not have.
    """

    __slots__ = ("_excluded", "_name_prefix", "_prefix", "_prefixable", "_resource", "_routes")

    _resource: str
    _routes: RouteCollection
    _prefixable: bool
    _prefix: str
    _name_prefix: str
    _excluded: tuple[str, ...]

    def __init__(self, resource: str, routes: RouteCollection, *, prefixable: bool) -> None:
        """Import ``routes``, the routes the loader of ``resource`` returned."""
        self._resource = resource
        self._routes = routes
        self._prefixable = prefixable
        self._prefix = ""
        self._name_prefix = ""
        self._excluded = ()

    def prefix(self, prefix: str) -> Self:
        """Put the routes under a path prefix.

        Raises:
            InvalidArgumentError: The resource's routes are at a place a
                standard fixes.
        """
        if not self._prefixable and prefix.strip().strip("/"):
            raise InvalidArgumentError(
                f'The routes of "{self._resource}" are at a place a standard fixes, '
                f'so they cannot be moved under "{prefix}".'
            )
        self._prefix = prefix
        return self

    def name_prefix(self, prefix: str) -> Self:
        """Prefix every route name, so two resources' names cannot collide."""
        self._name_prefix = prefix
        return self

    def exclude(self, *names: str) -> Self:
        """Leave routes out by name.

        Raises:
            InvalidArgumentError: The resource has no route of one of the names.
        """
        known = self._routes.all().keys() | self._routes.get_aliases().keys()
        unknown = [name for name in names if name not in known]
        if unknown:
            raise InvalidArgumentError(
                f'The routes of "{self._resource}" include no {", ".join(map(repr, unknown))}; '
                f"they are {', '.join(map(repr, sorted(known)))}."
            )
        self._excluded = (*self._excluded, *names)
        return self

    def apply_to(self, collection: RouteCollection) -> None:
        """Add the imported routes, arranged as asked, to ``collection``."""
        routes = self._routes.copy()
        routes.remove(*self._excluded)
        routes.add_prefix(self._prefix)
        if self._name_prefix:
            routes.add_name_prefix(self._name_prefix)
        collection.add_collection(routes)
