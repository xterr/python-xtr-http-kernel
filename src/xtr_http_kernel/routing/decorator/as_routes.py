"""Declaring a function as one of the application's routes files.

An application registers the routes it serves in ``config/routes/*.py``::

    @as_routes
    def webhook(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
        app.include_router(resources["webhook"], prefix="/hooks")

Every function so declared, in a module the kernel scans, is called by
``setup`` in scan order, with the application and the staged resources.
Nothing is mounted unless a routes file mounts it — routing is never
imported automatically.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Final, TypeAlias, cast

from xtr_http_kernel.routing.exception.invalid_argument_error import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from fastapi import APIRouter, FastAPI

__all__ = ["ROUTES_ATTRIBUTE", "RoutesFile", "as_routes", "routes_files_of"]

#: Where the declaration is kept on the function.
ROUTES_ATTRIBUTE: Final = "__xtr_routes__"

RoutesFile: TypeAlias = "Callable[[FastAPI, Mapping[str, APIRouter]], None]"


def as_routes(target: RoutesFile, /) -> RoutesFile:
    """Declare ``target`` as a routes file: it includes what the application serves.

    Raises:
        InvalidArgumentError: ``target`` is not a plain function — a routes
            file is called by ``setup`` while the application is mounted, and
            a coroutine nothing awaits would register nothing.
    """
    if not inspect.isfunction(target) or inspect.iscoroutinefunction(target):
        raise InvalidArgumentError(
            "@as_routes decorates a plain function taking the application and its "
            f"resources; {getattr(target, '__qualname__', target)!s} is not one."
        )
    setattr(target, ROUTES_ATTRIBUTE, True)
    return target


def routes_files_of(obj: object) -> tuple[RoutesFile, ...]:
    """Return ``obj`` itself when it was declared a routes file, else nothing."""
    if not callable(obj) or isinstance(obj, type):
        return ()
    declared = getattr(obj, "__dict__", {}).get(ROUTES_ATTRIBUTE) is True
    # Only as_routes writes the attribute, on a function typed as a routes file.
    return (cast("RoutesFile", obj),) if declared else ()
