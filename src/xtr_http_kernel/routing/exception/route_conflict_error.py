"""A route the routes files mount collides with one the application declared itself."""

from __future__ import annotations

from .routing_error import RoutingError

__all__ = ["RouteConflictError"]


class RouteConflictError(RoutingError):
    """A route the routes files mount collides with one the application declared itself.

    The application's own route is never replaced and always answered first;
    to change what a resource serves on purpose, leave its route out of the
    routes file that includes it, or replace the service behind its endpoint.

    Attributes:
        name: The mounted route's name.
        path: The mounted route's path.
        declared: The name of the application's route it collides with.
        reason: What collides — the name, or a method at the same path.
    """

    name: str
    path: str
    declared: str
    reason: str

    def __init__(self, name: str, path: str, declared: str, reason: str) -> None:
        """Record both routes and what they share."""
        self.name = name
        self.path = path
        self.declared = declared
        self.reason = reason
        super().__init__(
            f'The route "{name}" ({path}) collides with the application\'s route "{declared}": '
            f"{reason}. Leave it out of the routes files to change what is served on purpose."
        )
