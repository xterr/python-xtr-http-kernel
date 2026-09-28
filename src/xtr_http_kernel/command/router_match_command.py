"""``router:match``: which route a path reaches, and which one nearly does."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast, final

from fastapi.routing import iter_route_contexts
from starlette.routing import Match
from xtr_console import ConsoleStyle, ExitCode, as_command, escape

from .route_description import RouteDescription
from .router_command import RouterCommand

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi.routing import RouteContext
    from starlette.types import Scope

__all__ = ["RouterMatchCommand"]


class _Matcher(Protocol):
    """What a route answers when a request is tried against it."""

    def matches(self, scope: Scope, /) -> tuple[Match, Scope]:
        """Return how well ``scope`` fits, and what the route reads out of it."""
        ...


def _matcher(context: RouteContext) -> _Matcher:
    """Read ``context`` as the route it stands in for.

    A context forwards what it is asked for to the route it describes, so it
    answers ``matches`` without declaring it; the hop through ``object`` is
    what says the shape is known rather than guessed.
    """
    return cast("_Matcher", cast("object", context))


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
        for context in iter_route_contexts(application.routes):
            match, child_scope = _matcher(context).matches(scope)
            if match is Match.FULL:
                _report(io, RouteDescription.of(context), child_scope)
                return ExitCode.SUCCESS
            if match is Match.PARTIAL and refused is None:
                refused = RouteDescription.of(context)
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
