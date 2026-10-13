"""Adding the kernel's route table to the application, in ``setup()``."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from fastapi import APIRouter
from starlette.routing import Match

from ._route_contexts import route_contexts
from .routing.exception.route_conflict_error import RouteConflictError
from .routing.route_collection import RouteCollection
from .routing.route_table_parameter import ROUTE_TABLE_PARAMETER

if TYPE_CHECKING:
    from fastapi import FastAPI
    from starlette.types import Scope
    from xtr_dependency_injection.kernel.compiled_kernel import CompiledKernel

    from ._route_contexts import RouteView
    from .routing.route import Route

__all__ = ["mount_routes"]

_PARAMETER: Final = re.compile(r"\{([^}:]+)(?::([^}]+))?\}")
#: A value each kind of path parameter accepts, to ask the application's own
#: routes whether they would answer a contributed path first.
_SAMPLES: Final = {
    "int": "1",
    "float": "1.0",
    "uuid": "00000000-0000-0000-0000-000000000000",
}


def mount_routes(app: FastAPI, compiled: CompiledKernel) -> RouteCollection | None:
    """Include the compiled kernel's route table in ``app``, and return it.

    The routes are added with the framework's own ``include_router``, so each
    behaves exactly like the same function declared on a router; an alias is
    added too, under its own name and left out of the API description, so
    ``url_path_for`` reaches it. A kernel without the http_kernel bundle has no
    table and adds nothing.

    Raises:
        RouteConflictError: A contributed route shares a name with a route the
            application declared, or a route the application declared answers
            its method and path first; or two contributed routes answer the
            same method and path, so the second could never be reached.
    """
    container = compiled.container
    if not container.has_parameter(ROUTE_TABLE_PARAMETER):
        return None
    table = container.get_parameter(ROUTE_TABLE_PARAMETER)
    if not isinstance(table, RouteCollection):
        return None
    routes = list(table)
    aliases = [
        (name, route) for name in table.get_aliases() if (route := table.get(name)) is not None
    ]
    _refuse_shadowed(routes)
    _refuse_conflicts(app, [*routes, *aliases])
    included = APIRouter()
    for name, route in routes:
        _add(included, name, route, include_in_schema=route.include_in_schema)
    for name, route in aliases:
        _add(included, name, route, include_in_schema=False)
    if routes:
        app.include_router(included)
    return table


def _add(router: APIRouter, name: str, route: Route, *, include_in_schema: bool) -> None:
    router.add_api_route(
        route.path,
        route.endpoint,
        methods=list(route.methods) or None,
        name=name,
        include_in_schema=include_in_schema,
        tags=list(route.tags) or None,
        summary=route.summary,
        status_code=route.status_code,
        response_model=route.response_model,
    )


def _methods(route: Route) -> frozenset[str]:
    return frozenset(route.methods or ("GET",))


def _refuse_shadowed(table: list[tuple[str, Route]]) -> None:
    """Refuse two contributed routes answering the same method at the same path."""
    seen: dict[tuple[str, str], str] = {}
    for name, route in table:
        shape = _PARAMETER.sub("{}", route.path)
        for method in _methods(route):
            first = seen.setdefault((method, shape), name)
            if first != name:
                reason = f"both answer {method} {route.path}, so this one is never reached"
                raise RouteConflictError(name, route.path, first, reason)


def _refuse_conflicts(app: FastAPI, table: list[tuple[str, Route]]) -> None:
    """Refuse a contributed route the application's own routes collide with."""
    # Every route the application holds, those of routers it included too.
    declared = route_contexts(app.router.routes)
    for name, route in table:
        sample = _PARAMETER.sub(_sample, route.path)
        for own in declared:
            if own.name is not None and own.name == name:
                raise RouteConflictError(name, route.path, own.name, "they share the name")
            for method in sorted(_methods(route)):
                if _answers(own, sample, method):
                    reason = f"it answers {method} {route.path} first"
                    raise RouteConflictError(name, route.path, own.name or str(own.path), reason)


def _sample(match: re.Match[str]) -> str:
    return _SAMPLES.get(match.group(2) or "", "x")


def _answers(own: RouteView, path: str, method: str) -> bool:
    scope: Scope = {"type": "http", "path": path, "root_path": "", "method": method}
    matched, _child = own.matches(scope)
    return matched is Match.FULL
