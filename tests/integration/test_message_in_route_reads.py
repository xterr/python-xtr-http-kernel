"""Reading the request inside the route: the same answers with the message on it.

A route is free to read the body itself — ``body()``, ``json()``, ``form()``
or ``stream()`` — and asking for the request as a message must not change a
single one of those answers. Each route is served twice, once with the
message on its signature and once without, and the two answers are compared
byte for byte.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from xtr_dependency_injection import Injected

# Read at runtime: the framework evaluates a route's annotations.
from xtr_http_message_contracts import ServerRequestInterface

from tests.support.message_apps import message_kernel
from tests.support.message_counting import BUILT
from tests.support.serving import serving
from xtr_http_kernel import setup

pytestmark = pytest.mark.anyio

_TEXT = "text/plain"
_JSON = "application/json"
_FORM = "application/x-www-form-urlencoded"


@pytest.fixture(autouse=True)
def _clear_builds() -> None:
    BUILT.clear()


async def _read_body(request: Request) -> dict[str, object]:
    return {"body": (await request.body()).decode()}


async def _read_json(request: Request) -> dict[str, object]:
    return {"json": await request.json()}


async def _read_form(request: Request) -> dict[str, object]:
    form = await request.form()
    return {"form": {name: value for name, value in form.items() if isinstance(value, str)}}


async def _read_stream(request: Request) -> dict[str, object]:
    chunks = [chunk async for chunk in request.stream()]
    return {"stream": b"".join(chunks).decode()}


def _plain_application() -> FastAPI:
    app = FastAPI()

    @app.post("/body")
    async def body(request: Request) -> dict[str, object]:
        return await _read_body(request)

    @app.post("/json")
    async def json(request: Request) -> dict[str, object]:
        return await _read_json(request)

    @app.post("/form")
    async def form(request: Request) -> dict[str, object]:
        return await _read_form(request)

    @app.post("/stream")
    async def stream(request: Request) -> dict[str, object]:
        return await _read_stream(request)

    setup(app, message_kernel())
    return app


def _marked_application() -> FastAPI:
    """The same four routes, each also asking for the request as a message."""
    app = FastAPI()

    @app.post("/body")
    async def body(
        request: Request, message: Injected[ServerRequestInterface]
    ) -> dict[str, object]:
        del message
        return await _read_body(request)

    @app.post("/json")
    async def json(
        request: Request, message: Injected[ServerRequestInterface]
    ) -> dict[str, object]:
        del message
        return await _read_json(request)

    @app.post("/form")
    async def form(
        request: Request, message: Injected[ServerRequestInterface]
    ) -> dict[str, object]:
        del message
        return await _read_form(request)

    @app.post("/stream")
    async def stream(
        request: Request, message: Injected[ServerRequestInterface]
    ) -> dict[str, object]:
        del message
        return await _read_stream(request)

    setup(app, message_kernel())
    return app


async def _answer(app: FastAPI, path: str, body: bytes, media_type: str) -> tuple[int, bytes]:
    """Return the status and the body of posting ``body`` at ``path``."""
    async with serving(app) as client:
        response = await client.post(path, content=body, headers={"content-type": media_type})
    return response.status_code, response.content


@pytest.mark.parametrize(
    ("path", "body", "media_type"),
    [
        pytest.param("/body", b"two words", _TEXT, id="body"),
        pytest.param("/json", b'{"title":"dune","pages":412}', _JSON, id="json"),
        pytest.param("/form", b"title=dune&pages=412", _FORM, id="form"),
        pytest.param("/stream", b"two words", _TEXT, id="stream"),
    ],
)
async def test_a_route_reading_the_body_itself_answers_the_same_either_way(
    path: str, body: bytes, media_type: str
) -> None:
    plain = await _answer(_plain_application(), path, body, media_type)

    assert BUILT == []

    marked = await _answer(_marked_application(), path, body, media_type)
    built = list(BUILT)

    assert marked == plain
    assert plain[0] == 200
    # The route reads its body itself. A body with a parsed side — JSON, a
    # form — the container has read by the time it hands the message on, and
    # the route's own read shares that one; a raw body is left to the route
    # alone, and nothing is materialised for it.
    assert built == ([path] if media_type in (_JSON, _FORM) else [])
