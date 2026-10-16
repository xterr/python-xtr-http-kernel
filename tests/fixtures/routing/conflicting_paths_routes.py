"""A routes file including two resources that answer one method at one path."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import APIRouter, FastAPI


@as_routes
def conflicting_paths(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
    """Include the books and the shelf: both answer GET /books."""
    app.include_router(resources["books"])
    app.include_router(resources["shelf"])
