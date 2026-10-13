"""Who reads the body first, and what the files that came with it are good for.

The framework reads a submitted body before it resolves anything a route
declared, so a route with body parameters has the framework read first and
the message built from what it cached; a route with none leaves the message
the first reader. Both orders must give the message the same fields — and the
files must still be open while the route holds them, and shut once the
request's scope has closed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Final, cast

import pytest
from fastapi import FastAPI, File, Form, UploadFile
from starlette.datastructures import FormData
from xtr_dependency_injection import Injected

# Read at runtime: the framework evaluates a route's annotations.
from xtr_http_message_contracts import ServerRequestInterface

from tests.support.message_apps import message_kernel
from tests.support.message_counting import BUILT
from tests.support.serving import serving
from xtr_http_kernel import setup

if TYPE_CHECKING:
    from xtr_http_message_contracts import UploadedFileInterface

pytestmark = pytest.mark.anyio

HELD: Final[list[UploadFile]] = []
"""The uploaded file each route held, so a test can look at it afterwards."""


@pytest.fixture(autouse=True)
def _clear_journals() -> None:
    BUILT.clear()
    HELD.clear()


def _fields_of(message: ServerRequestInterface) -> dict[str, str]:
    """Return the message's parsed body as plain text fields."""
    form = cast("FormData", message.get_parsed_body())
    return {name: value for name, value in form.items() if isinstance(value, str)}


def _application() -> FastAPI:
    app = FastAPI()

    @app.post("/read-first")
    async def read_first(
        title: Annotated[str, Form()],
        message: Injected[ServerRequestInterface],
    ) -> dict[str, object]:
        return {
            "title": title,
            "fields": _fields_of(message),
            "body": await message.get_body().get_contents(),
        }

    @app.post("/message-first")
    async def message_first(message: Injected[ServerRequestInterface]) -> dict[str, object]:
        return {
            "fields": _fields_of(message),
            "body": await message.get_body().get_contents(),
        }

    @app.post("/files")
    async def files(message: Injected[ServerRequestInterface]) -> dict[str, object]:
        form = cast("FormData", message.get_parsed_body())
        HELD.append(cast("UploadFile", form["doc"]))
        doc = cast("UploadedFileInterface", message.get_uploaded_files()["doc"])
        return {
            "name": doc.get_client_filename(),
            "type": doc.get_client_media_type(),
            "size": doc.get_size(),
            "content": (await doc.get_stream().get_contents()).decode(),
        }

    setup(app, message_kernel())
    return app


async def test_the_framework_reads_a_declared_body_before_the_message_is_built() -> None:
    async with serving(_application()) as client:
        response = await client.post("/read-first", data={"title": "dune", "pages": "412"})

    # The form the framework parsed is the one the message carries, and the
    # message's body is empty because that form consumed it.
    assert response.json() == {
        "title": "dune",
        "fields": {"title": "dune", "pages": "412"},
        "body": "",
    }
    assert BUILT == ["/read-first"]


async def test_the_message_is_the_first_reader_when_the_route_declares_no_body() -> None:
    async with serving(_application()) as client:
        response = await client.post("/message-first", data={"title": "dune", "pages": "412"})

    assert response.json() == {"fields": {"title": "dune", "pages": "412"}, "body": ""}
    assert BUILT == ["/message-first"]


async def test_an_uploaded_file_is_readable_while_the_route_holds_it() -> None:
    async with serving(_application()) as client:
        response = await client.post(
            "/files", files={"doc": ("notes.txt", b"hello files", "text/plain")}
        )

    assert response.json() == {
        "name": "notes.txt",
        "type": "text/plain",
        "size": 11,
        "content": "hello files",
    }


async def test_an_uploaded_file_is_shut_once_the_request_scope_has_closed() -> None:
    async with serving(_application()) as client:
        response = await client.post(
            "/files", files={"doc": ("notes.txt", b"hello files", "text/plain")}
        )

    assert response.status_code == 200
    assert HELD[0].file.closed


async def test_a_declared_file_and_field_are_the_framework_s_own_in_the_message() -> None:
    app = FastAPI()

    @app.post("/both")
    async def both(
        note: Annotated[str, Form()],
        doc: Annotated[UploadFile, File()],
        message: Injected[ServerRequestInterface],
    ) -> dict[str, object]:
        return {
            "read": (await doc.read()).decode(),
            "parsed": isinstance(message.get_parsed_body(), FormData),
            "declared": note,
            "in_message": _fields_of(message)["note"],
        }

    setup(app, message_kernel())

    async with serving(app) as client:
        response = await client.post(
            "/both", data={"note": "keep"}, files={"doc": ("a.txt", b"body", "text/plain")}
        )

    # The framework read the file first; the message wraps what it parsed,
    # which leaves the route's own read of the file untouched.
    assert response.json() == {
        "read": "body",
        "parsed": True,
        "declared": "keep",
        "in_message": "keep",
    }
