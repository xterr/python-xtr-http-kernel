"""The routes file a bundle's recipe would write: the books routes under /shop."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import APIRouter, FastAPI


@as_routes
def books(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
    """Serve the books under /shop, at their own names."""
    app.include_router(resources["books"], prefix="/shop")
