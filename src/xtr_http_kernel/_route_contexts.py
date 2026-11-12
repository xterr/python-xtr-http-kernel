"""One view of an application's routes, every prefix applied.

The framework keeps a router included under a prefix as a wrapper around that
router rather than as the routes it holds, and offers the effective view of
every route — prefixes applied — through ``iter_route_contexts``. This module
is the only place that reads it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast, final

from fastapi.routing import iter_route_contexts

if TYPE_CHECKING:
    from collections.abc import Sequence

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
            the route.
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
    """Read every route of an application, prefixes applied."""
    return [_of_context(context) for context in iter_route_contexts(routes)]


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
