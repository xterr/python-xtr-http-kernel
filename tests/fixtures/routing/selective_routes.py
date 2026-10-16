"""A routes file including one resource and leaving the rest unregistered."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import APIRouter, FastAPI


@as_routes
def selective(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
    """Include only the well-known document; a resource no file includes is not served."""
    app.include_router(resources["well_known"])
