"""``debug:router``: every route of an application, as routing reads them."""

from __future__ import annotations

from typing import final

from fastapi.routing import iter_route_contexts
from xtr_console import ConsoleStyle, ExitCode, as_command, escape

from .route_description import RouteDescription
from .router_command import RouterCommand

__all__ = ["DebugRouterCommand"]


@as_command("debug:router")
@final
class DebugRouterCommand(RouterCommand):
    """Lists every route an application holds, in the order routing tries them."""

    __slots__ = ()

    async def __call__(self, io: ConsoleStyle, *, app: str | None = None) -> int:
        """List the application's routes, prefixes applied.

        A router included under a prefix is listed under it, and a mounted
        application is listed as the one route that reaches it — which is
        what routing sees.

        Args:
            io: Where the command writes.
            app: The application to read, as ``package.module:app``; the
                configured one when left out.
        """
        application = self._app_or_report(io, app)
        if application is None:
            return ExitCode.INVALID
        described = [
            RouteDescription.of(context) for context in iter_route_contexts(application.routes)
        ]
        io.section(f"Routes ({len(described)})")
        io.table(
            ("Methods", "Path", "Name", "Endpoint"),
            [
                (
                    escape(route.methods),
                    escape(route.path),
                    escape(route.name),
                    escape(route.endpoint),
                )
                for route in described
            ],
        )
        return ExitCode.SUCCESS
