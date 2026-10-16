"""A routes file arranging a resource: renamed, moved, and one route of the app's own."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import APIRouter, FastAPI


@as_routes
def arranged(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
    """Move the books under /shop under renamed names, and answer / as home."""
    books = resources["books"]
    for route in books.routes:
        # The framework's base route type does not declare the name every kind carries.
        route.name = f"shop_{route.name}"  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]  # ty: ignore[unresolved-attribute]
    app.include_router(books, prefix="/shop")
    app.include_router(resources["well_known"])

    @app.get("/", name="home")
    async def home() -> dict[str, str]:
        return {"home": "page"}
