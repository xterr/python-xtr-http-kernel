"""A routes file including one resource twice."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import APIRouter, FastAPI


@as_routes
def twice(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
    """Include the books twice: every name of them lands on the app twice."""
    app.include_router(resources["books"])
    app.include_router(resources["books"])
