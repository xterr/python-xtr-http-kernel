"""A routes file including every staged resource — the tests' stand-in for arrangement."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import APIRouter, FastAPI


@as_routes
def included(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
    """Include every resource at its own paths, in staging order."""
    for router in resources.values():
        app.include_router(router)
