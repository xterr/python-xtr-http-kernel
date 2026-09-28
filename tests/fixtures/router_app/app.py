"""One application carrying every route kind the commands have to report on.

The routes are here for their shape, not their answers: a router included
under a prefix, a route taking a path parameter, one answering a single
method, a connection route and a mounted sub-router.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, WebSocket
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route, Router

books = APIRouter(prefix="/books")
"""Included under its prefix, so the listing has to report the prefixed path."""


@books.get("/{isbn}")
async def book(isbn: str) -> dict[str, str]:
    """Answer with the book an ISBN names."""
    return {"isbn": isbn}


async def ping(request: Request) -> PlainTextResponse:
    """The mounted sub-router's only route."""
    del request
    return PlainTextResponse("pong")


app = FastAPI()
app.include_router(books)


@app.post("/orders")
async def place_order() -> dict[str, str]:
    """Take an order — this method and no other."""
    return {"order": "placed"}


@app.websocket("/live")
async def live(websocket: WebSocket) -> None:
    """Hold a connection open."""
    await websocket.accept()
    await websocket.close()


app.mount("/inner", Router(routes=[Route("/ping", ping)]), name="inner")
