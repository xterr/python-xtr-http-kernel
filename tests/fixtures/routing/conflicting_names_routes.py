"""A routes file including two resources contributing one route name."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import APIRouter, FastAPI


@as_routes
def conflicting_names(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
    """Include the books and the library: both contribute books_list."""
    app.include_router(resources["books"])
    app.include_router(resources["library"])
