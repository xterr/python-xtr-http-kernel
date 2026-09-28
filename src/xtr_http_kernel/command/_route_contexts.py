"""One view of an application's routes, whichever way the framework hands them over.

Newer releases keep a router included under a prefix as a wrapper around that
router rather than as the routes it holds, and offer the effective view of
every route — prefixes applied — through ``iter_route_contexts``. Older ones
put each route in the list directly, already effective. This module is the
only place that difference lives.

A release that grew the wrapper before it grew the view of one lists an
included router as the single opaque route the application holds: there is no
supported way in, so the row names the wrapper for what it is rather than
inventing a path for it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast, final

from fastapi import routing as fastapi_routing
from starlette.routing import Host, Mount, Route, WebSocketRoute

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from fastapi.routing import RouteContext
    from starlette.routing import BaseRoute, Match
    from starlette.types import Scope

__all__ = ["RouteView", "route_contexts"]


class _Matcher(Protocol):
    """What answers whether a request reaches a route."""

    def matches(self, scope: Scope, /) -> tuple[Match, Scope]:
        """Return how well ``scope`` fits, and what the route reads out of it."""
        ...


@final
@dataclass(frozen=True, slots=True)
class RouteView:
    """What routing sees for one route, every prefix already applied.

    Attributes:
        route: The route itself, for what only its kind can answer.
        path: The path requests are matched against, ``None`` for a route the
            framework keeps to itself.
        name: The name the route answers to, ``None`` when it has none.
        methods: The methods it answers, ``None`` when it takes whatever
            arrives or is not a method route at all.
        endpoint: What it hands the request to, ``None`` when it hands it to
            another application instead.
        matcher: What answers :meth:`matches` — the framework's own view of
            the route, or the route itself.
    """

    route: BaseRoute
    path: str | None
    name: str | None
    methods: set[str] | None
    endpoint: object | None
    matcher: object

    def matches(self, scope: Scope) -> tuple[Match, Scope]:
        """Return how well ``scope`` fits this route, and what it reads out of it.

        The framework's own view of a route stands in for it and forwards what
        it is asked for, so it answers this without declaring it; the hop
        through ``object`` is what says the shape is known rather than guessed.
        """
        return cast("_Matcher", self.matcher).matches(scope)


def route_contexts(routes: Sequence[BaseRoute]) -> Sequence[RouteView]:
    """Read every route of an application, prefixes applied.

    A release offering the effective view of each route is asked for it; the
    rest hand their routes over already effective.
    """
    effective = cast(
        "Callable[[Sequence[BaseRoute]], Iterable[RouteContext]] | None",
        getattr(fastapi_routing, "iter_route_contexts", None),
    )
    if effective is None:
        return [_of_route(route) for route in routes]
    return [_of_context(context) for context in effective(routes)]


def _of_context(context: RouteContext) -> RouteView:
    """Read the framework's own view of a route."""
    return RouteView(
        route=context.route,
        path=context.path,
        name=context.name,
        methods=context.methods,
        endpoint=context.endpoint,
        matcher=context,
    )


def _of_route(route: BaseRoute) -> RouteView:
    """Read a route a release hands over already effective.

    Each line below names the kinds of route that can answer that much; a kind
    that answers none of it is left to be named by itself.
    """
    methods = route.methods if isinstance(route, Route) else None
    endpoint = route.endpoint if isinstance(route, (Route, WebSocketRoute)) else None
    path = route.path if isinstance(route, (Mount, Route, WebSocketRoute)) else None
    name = route.name if isinstance(route, (Host, Mount, Route, WebSocketRoute)) else None
    return RouteView(route, path, name, methods, endpoint, route)
