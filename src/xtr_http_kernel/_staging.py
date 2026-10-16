"""Staging the discovered route resources, and running the application's routes files.

``setup`` calls this once, after the kernel is built: every resource is staged
into a router of its own, the routes files include what the application serves
— nothing is mounted unless a file mounts it — and what the files mounted is
refused when it collides with the routes the application declared itself.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final, cast

from fastapi import APIRouter

from ._route_contexts import route_contexts
from .routing.exception.invalid_argument_error import InvalidArgumentError
from .routing.exception.route_conflict_error import RouteConflictError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from fastapi import FastAPI
    from starlette.routing import BaseRoute

    from ._route_contexts import RouteView
    from .routing.decorator.as_routes import RoutesFile
    from .routing.route_registry import RouteRegistry

__all__ = ["mount_routes"]

_PARAMETER: Final = re.compile(r"\{[^}:]+(?::[^}]+)?\}")


def mount_routes(app: FastAPI, registry: RouteRegistry) -> None:
    """Stage the registry's route resources into ``app``, as its routes files include them.

    A resource no routes file includes is staged and dropped: routing is
    never imported automatically.

    Raises:
        InvalidArgumentError: Two routes of one resource claim one name, or a
            routes file includes a resource nothing installed contributes.
        RouteConflictError: A mounted route shares a name with one the
            application declared, answers a method at the path shape of one
            the application declared, or answers a method at the path shape of
            another mounted route.
    """
    resources = _stage(registry.resources)
    own = route_contexts(app.router.routes)
    for file in registry.files:
        _run(app, resources, file)
    _refuse_conflicts(app, own)


def _stage(entries: Sequence[tuple[str, Callable[[APIRouter], None]]]) -> dict[str, APIRouter]:
    """Return one staged router per resource, refusing a name claimed twice."""
    staged: dict[str, APIRouter] = {}
    claimed: dict[str, dict[str, str]] = {}
    for resource, function in entries:
        router = staged.setdefault(resource, APIRouter())
        names = claimed.setdefault(resource, {})
        before = len(router.routes)
        function(router)
        where = _where(function)
        for route in router.routes[before:]:
            name = _name_of(route) or ""
            if name in names:
                raise InvalidArgumentError(
                    f'Two routes of the resource "{resource}" are named "{name}": '
                    f"{names[name]} declares one and {where} the other. "
                    "Give one of them a name of its own."
                )
            names[name] = where
    return staged


def _run(app: FastAPI, resources: Mapping[str, APIRouter], file: RoutesFile) -> None:
    """Run one routes file, naming the resource it asks for that nothing contributes."""
    try:
        file(app, resources)
    except KeyError as error:
        missing = error.args[0] if error.args else "?"
        raise InvalidArgumentError(
            f"The routes file {_where(file)} asks for the route resource {missing!r}, "
            "which nothing installed contributes — is the package that ships it "
            "installed, and its bundle listed in BUNDLES?"
        ) from error


def _refuse_conflicts(app: FastAPI, own: Sequence[RouteView]) -> None:
    """Refuse a mounted route colliding with the application's own, or with another.

    The application's own routes are whatever it held before the files ran;
    they are never changed, and they come first. A mounted route sharing a
    name with one of them, or answering one of their methods at their path
    shape — parameters told apart by shape, not by name — is refused here
    rather than silently shadowed or shadowing. So is a second mounted route
    answering a method and shape a first one already answers, which no request
    could ever reach past it.
    """
    own_ids = {id(view.route) for view in own}
    mounted = [view for view in route_contexts(app.router.routes) if id(view.route) not in own_ids]
    own_names = {view.name for view in own if view.name is not None}
    own_shapes = [
        (_shape(view.path), view.methods, view.name or view.path)
        for view in own
        if view.path is not None
    ]
    names: dict[str, str] = {}
    shapes: list[tuple[str, set[str] | None, str]] = []
    for view in mounted:
        if view.path is None:
            continue
        shape = _shape(view.path)
        methods = view.methods or None
        label = view.name or view.path
        if view.name is not None:
            if view.name in own_names:
                raise RouteConflictError(view.name, view.path, view.name, "they share the name")
            if (previous := names.get(view.name)) is not None:
                raise RouteConflictError(
                    view.name,
                    view.path,
                    previous,
                    "it is mounted twice — a routes file includes its resource twice, "
                    "or two resources contribute the name",
                )
            names[view.name] = view.path
        for own_methods, declared in ((m, d) for s, m, d in own_shapes if s == shape):
            if _overlap(methods, own_methods):
                raise RouteConflictError(
                    label,
                    view.path,
                    declared,
                    f"it answers {_shared_method(methods, own_methods)} {view.path} first",
                )
        for other_shape, other_methods, other_path in shapes:
            if other_shape == shape and _overlap(methods, other_methods):
                raise RouteConflictError(
                    label,
                    view.path,
                    other_path,
                    f"both answer {_shared_method(methods, other_methods)} {view.path}, "
                    "so this one is never reached",
                )
        shapes.append((shape, methods, view.path))


def _shape(path: str) -> str:
    """Return the path with every parameter reduced to one shape, names forgotten."""
    return _PARAMETER.sub("{}", path)


def _overlap(one: set[str] | None, other: set[str] | None) -> bool:
    """Tell whether two method sets can answer one method; ``None`` answers all."""
    return one is None or other is None or not one.isdisjoint(other)


def _shared_method(one: set[str] | None, other: set[str] | None) -> str:
    """Name one method both answer, for the refusal that names it."""
    if one is not None and other is not None:
        return min(one & other)
    methods = one if one is not None else other
    return min(methods) if methods else "whatever arrives"


def _name_of(route: BaseRoute) -> str | None:
    """Return the name a route answers to; the framework's base type does not declare one."""
    return cast("str | None", getattr(route, "name", None))


def _where(function: object) -> str:
    """Name a function for an error: its qualname, or itself."""
    return str(getattr(function, "__qualname__", function))
