"""``router:match``: which route a path reaches, and which one nearly does."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from starlette.routing import Match
from xtr_console import ConsoleStyle, ExitCode, as_command, escape

from ._route_contexts import route_contexts
from .route_description import RouteDescription
from .router_command import RouterCommand

if TYPE_CHECKING:
    from collections.abc import Mapping

    from starlette.types import Scope

__all__ = ["RouterMatchCommand"]


@as_command("router:match")
@final
class RouterMatchCommand(RouterCommand):
    """Names the route a path and a method reach, without serving anything.

    The routes are tried against a request that is built and thrown away —
    nothing is sent, no endpoint runs, and the application is left as it was.
    """

    __slots__ = ()

    async def __call__(
        self,
        io: ConsoleStyle,
        path: str,
        *,
        method: str = "GET",
        app: str | None = None,
    ) -> int:
        """Report the route ``path`` reaches with ``method``.

        Exits successfully on a route that answers. A route matching the
        path but refusing the method is reported as the near miss it is, and
        so is a path no route answers at all — both fail the run.

        Args:
            io: Where the command writes.
            path: The path to try, as it would arrive.
            method: The method to try it with.
            app: The application to read, as ``package.module:app``; the
                configured one when left out.
        """
        application = self._app_or_report(io, app)
        if application is None:
            return ExitCode.INVALID
        wanted = method.upper()
        scope: Scope = {"type": "http", "method": wanted, "path": path, "root_path": ""}
        refused: RouteDescription | None = None
        for view in route_contexts(application.routes):
            match, child_scope = view.matches(scope)
            if match is Match.FULL:
                _report(io, RouteDescription.of(view), child_scope)
                return ExitCode.SUCCESS
            if match is Match.PARTIAL and refused is None:
                refused = RouteDescription.of(view)
        if refused is not None:
            io.error(
                f'"{escape(path)}" reaches the route "{escape(refused.name)}" '
                f"({escape(refused.path)}), which does not answer {escape(wanted)}"
            )
            return ExitCode.FAILURE
        io.error(f"no route matches {escape(wanted)} {escape(path)}")
        return ExitCode.FAILURE


def _report(io: ConsoleStyle, route: RouteDescription, child_scope: Scope) -> None:
    """Say which route answered, and what it read out of the path."""
    io.success(f'"{escape(route.path)}" is answered by {escape(route.endpoint)}')
    io.table(
        ("Name", "Methods", "Path", "Endpoint"),
        [
            (
                escape(route.name),
                escape(route.methods),
                escape(route.path),
                escape(route.endpoint),
            )
        ],
    )
    parameters = cast("Mapping[str, object]", child_scope.get("path_params", {}))
    if parameters:
        io.table(
            ("Parameter", "Value"),
            [(escape(name), escape(str(value))) for name, value in sorted(parameters.items())],
        )
