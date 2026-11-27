"""An application whose description holds everything the export reshapes.

Two tags, so a filter keeps one; a generic page, whose schema name a gateway
refuses; a read-only property; and a query parameter named with brackets.
The description is not ASCII, so the export has to keep it as written.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field


class Book(BaseModel):
    """A book of the catalogue."""

    isbn: Annotated[str, Field(json_schema_extra={"readOnly": True})]
    title: str


class Page[ItemT](BaseModel):
    """One page of a listing."""

    items: list[ItemT]


app = FastAPI(
    title="Librairie",
    description="Le catalogue — livres et commandes",
    openapi_tags=[{"name": "books"}, {"name": "orders"}],
)


@app.get("/books", tags=["books"])
async def list_books(
    title: Annotated[str | None, Query(alias="filter[title]")] = None, page: int = 1
) -> Page[Book]:
    """List the books, a page at a time."""
    del title, page
    return Page[Book](items=[])


@app.post("/orders", tags=["orders"])
async def place_order() -> dict[str, str]:
    """Take an order."""
    return {"order": "placed"}
