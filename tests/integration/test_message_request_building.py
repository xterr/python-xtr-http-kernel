"""A served application where only some routes ask for the request as a message.

The count comes from a bundle putting a counting factory in front of the
bridge's own, so it counts builds that really happened inside the container.
A route that does not ask must leave it empty — and the biggest of them must
leave the memory of the process alone too, which is measured where the
buffering would happen: in the application, not in the client, whose own
transport holds every response it reads.
"""

from __future__ import annotations

import json
import tracemalloc
from typing import TYPE_CHECKING, Annotated, Final

import pytest
from fastapi import FastAPI, File, Request, UploadFile
from xtr_dependency_injection import Injected

# Read at runtime: the framework evaluates a route's annotations.
from xtr_http_message_contracts import ServerRequestInterface

from tests.support.asgi_requests import asgi_scope
from tests.support.asgi_responses import body_of
from tests.support.message_apps import message_kernel
from tests.support.message_counting import BUILT
from tests.support.serving import driving, serving
from xtr_http_kernel import setup

if TYPE_CHECKING:
    from starlette.types import Message, Receive

pytestmark = pytest.mark.anyio

_CHUNK: Final = 64 * 1024
"""How much of the big upload arrives at a time."""

_CHUNKS: Final = 320
"""Enough chunks to make 20 MiB."""

_BUDGET: Final = 4 * 1024 * 1024
"""What the big upload may allocate at its peak: a small multiple of a chunk.

Far below the 20 MiB it carries, so a route that buffered the body — or a
factory that built a message out of it — would go straight through this, and
far above what reading it a chunk at a time costs.
"""


@pytest.fixture(autouse=True)
def _clear_builds() -> None:
    BUILT.clear()


def _application() -> FastAPI:
    app = FastAPI()

    @app.get("/plain")
    async def plain() -> dict[str, str]:
        return {"plain": "yes"}

    @app.post("/upload")
    async def upload(doc: Annotated[UploadFile, File()]) -> dict[str, int]:
        return {"length": len(await doc.read())}

    @app.post("/streamed")
    async def streamed(request: Request) -> dict[str, int]:
        length = 0
        async for chunk in request.stream():
            length += len(chunk)
        return {"length": length}

    @app.get("/asked")
    async def asked(message: Injected[ServerRequestInterface]) -> dict[str, str]:
        return {"path": message.get_uri().get_path()}

    @app.post("/asked-streamed")
    async def asked_streamed(message: Injected[ServerRequestInterface]) -> dict[str, int]:
        return {"length": len(await message.get_body().get_contents())}

    setup(app, message_kernel())
    return app


def _chunked_body() -> tuple[Receive, int]:
    """Return a receive channel handing 20 MiB over in chunks, and how long that is."""
    remaining = _CHUNKS

    async def receive() -> Message:
        nonlocal remaining
        if remaining == 0:
            return {"type": "http.request", "body": b"", "more_body": False}
        remaining -= 1
        # A fresh payload each time: handing the same object over again would
        # allocate nothing, and so would prove nothing about what is held.
        return {"type": "http.request", "body": b"x" * _CHUNK, "more_body": True}

    return receive, _CHUNK * _CHUNKS


async def _peak_of(path: str) -> tuple[list[Message], int, int]:
    """Drive 20 MiB at ``path`` and return what was sent, its length, and the peak held."""
    receive, length = _chunked_body()
    scope = asgi_scope(
        "POST",
        path=path,
        headers=((b"host", b"served.test"), (b"content-type", b"application/octet-stream")),
    )

    async with driving(_application()) as drive:
        tracemalloc.start()
        try:
            tracemalloc.reset_peak()
            sent = await drive(scope, receive)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

    return sent, length, peak


async def test_a_plain_route_builds_no_request_message() -> None:
    async with serving(_application()) as client:
        response = await client.get("/plain")

    assert response.json() == {"plain": "yes"}
    assert BUILT == []


async def test_a_route_taking_an_uploaded_file_builds_no_request_message() -> None:
    async with serving(_application()) as client:
        response = await client.post("/upload", files={"doc": ("a.txt", b"hello", "text/plain")})

    assert response.json() == {"length": 5}
    assert BUILT == []


async def test_a_route_reading_the_body_as_a_stream_builds_no_request_message() -> None:
    async with serving(_application()) as client:
        response = await client.post("/streamed", content=b"four")

    assert response.json() == {"length": 4}
    assert BUILT == []


async def test_a_route_that_asks_builds_the_request_message_once() -> None:
    async with serving(_application()) as client:
        response = await client.get("/asked")

    assert response.json() == {"path": "/asked"}
    assert BUILT == ["/asked"]


async def test_a_twenty_megabyte_upload_is_neither_built_nor_buffered() -> None:
    sent, length, peak = await _peak_of("/streamed")

    assert json.loads(body_of(sent)) == {"length": length}
    assert BUILT == []
    assert peak < _BUDGET, f"the route held {peak} bytes of a {length}-byte body"


async def test_the_same_upload_is_held_whole_once_a_route_asks_for_it() -> None:
    # The control on the measurement above: a route that *does* ask is handed
    # the body, so the peak passes the whole of it. Were the measurement blind
    # to buffering, this would come in under the budget too.
    sent, length, peak = await _peak_of("/asked-streamed")

    assert json.loads(body_of(sent)) == {"length": length}
    assert BUILT == ["/asked-streamed"]
    assert peak > length
