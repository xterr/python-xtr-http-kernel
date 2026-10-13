"""Building the application's table from its routes files and the resources offered."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, final

from xtr_http_kernel.routing.exception.invalid_argument_error import InvalidArgumentError
from xtr_http_kernel.routing.route_collection import RouteCollection

from .configurator.routing_configurator import RoutingConfigurator

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

    from xtr_http_kernel.routing.decorator.as_routes import RoutesFile

__all__ = ["RoutesFileLoader"]


@final
class RoutesFileLoader:
    """Builds the route table from the routes files, given every resource's routes.

    Resources no file imports or skips come first, at their own paths and
    names, in the order they are offered; then each file's arrangement, in the
    order the files are given. Each file works on its own copy of every
    resource, so one file arranging a resource does not change what the next
    file imports.
    """

    __slots__ = ("_files",)

    _files: tuple[RoutesFile, ...]

    def __init__(self, files: Sequence[RoutesFile]) -> None:
        """Hold the routes files, in the order they are applied."""
        self._files = tuple(files)

    def load(
        self,
        resources: Mapping[str, RouteCollection],
        fixed: Collection[str] = (),
    ) -> RouteCollection:
        """Return the table the files arrange out of ``resources``.

        Args:
            resources: Each resource's routes by name, in the order to serve
                the ones no file mentions.
            fixed: The resources a standard puts at a fixed place, which no
                file may move under a prefix.

        Raises:
            InvalidArgumentError: A file names an unknown resource or route,
                prefixes a fixed resource, defines a route with no endpoint, is
                a coroutine function, or imports a resource another file skips;
                or two resources no file arranges contribute the same name.
        """
        configurators: list[RoutingConfigurator] = []
        fixed_resources = frozenset(fixed)
        for file in self._files:
            if inspect.iscoroutinefunction(file):
                raise InvalidArgumentError(
                    f"The routes file {getattr(file, '__qualname__', file)!s} is a coroutine "
                    "function; "
                    "routes files are plain functions, run while the kernel compiles."
                )
            configurator = RoutingConfigurator(
                {name: routes.copy() for name, routes in resources.items()}, fixed_resources
            )
            file(configurator)
            configurators.append(configurator)
        _refuse_skipped_and_imported(configurators)
        mentioned = frozenset[str]().union(
            *(configurator.mentioned for configurator in configurators)
        )
        table = RouteCollection()
        owners: dict[str, str] = {}
        for name, routes in resources.items():
            if name in mentioned:
                continue
            for route_name in routes.all().keys() | routes.get_aliases().keys():
                first = owners.setdefault(route_name, name)
                if first != name:
                    raise InvalidArgumentError(
                        f'The resources "{first}" and "{name}" both contribute a route named '
                        f'"{route_name}"; import one of them with a name_prefix in a routes file.'
                    )
            table.add_collection(routes.copy())
        for configurator in configurators:
            configurator.apply(table)
        return table


def _refuse_skipped_and_imported(configurators: list[RoutingConfigurator]) -> None:
    skipped = frozenset[str]().union(*(configurator.skipped for configurator in configurators))
    imported = frozenset[str]().union(*(configurator.imported for configurator in configurators))
    both = sorted(skipped & imported)
    if both:
        raise InvalidArgumentError(
            f"The resource {both[0]!r} is skipped by one routes file and imported by another; "
            "say which in one place."
        )
