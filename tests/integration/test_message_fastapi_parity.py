"""The framework's own body handling, with and without the message on the route.

``Form``, ``File`` beside ``Form``, a model body, an embedded model body and
a plain JSON body each go to two applications that differ in one thing: the
marked one also asks for the request as a message. Every answer — the status,
the headers as they go over the wire and the body byte for byte — must be the
same, for a payload the framework accepts and for every payload it refuses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Final

import httpx
import pytest
from fastapi import Body, FastAPI, File, Form, UploadFile
from pydantic import BaseModel
from xtr_dependency_injection import Injected

# Read at runtime: the framework evaluates a route's annotations.
from xtr_http_message_contracts import ServerRequestInterface

from tests.support.message_apps import message_kernel
from tests.support.message_counting import BUILT
from tests.support.serving import serving
from xtr_http_kernel import setup

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _clear_builds() -> None:
    BUILT.clear()


_ENCODE: Final = "http://encode.test/"
"""Where the client encodes a payload rather than sending it."""

_JSON: Final = "application/json"
_URLENCODED: Final = "application/x-www-form-urlencoded"
_REQUEST_ID: Final = b"x-request-id"

_BOUNDARY: Final = b"xtrmessageparity"
_MULTIPART: Final = f"multipart/form-data; boundary={_BOUNDARY.decode()}"
_PART: Final = b'Content-Disposition: form-data; name="'


class Book(BaseModel):
    """What a model body carries."""

    title: str
    pages: int


def _urlencoded(fields: Mapping[str, str]) -> bytes:
    """Return the body a client would send for a submitted form of ``fields``."""
    return httpx.Request("POST", _ENCODE, data=dict(fields)).content


def _multipart(fields: Mapping[str, str], files: Mapping[str, tuple[str, bytes, str]]) -> bytes:
    """Return the body a client would send for a form carrying files.

    Encoded here rather than by the client so that a form of fields alone is
    still a multipart form, and so that both applications are handed the very
    same bytes — boundary included.
    """
    lines: list[bytes] = []
    for name, value in fields.items():
        lines += [b"--" + _BOUNDARY, _PART + name.encode() + b'"', b"", value.encode()]
    for name, (filename, content, media_type) in files.items():
        lines += [
            b"--" + _BOUNDARY,
            _PART + name.encode() + b'"; filename="' + filename.encode() + b'"',
            b"Content-Type: " + media_type.encode(),
            b"",
            content,
        ]
    lines += [b"--" + _BOUNDARY + b"--", b""]
    return b"\r\n".join(lines)


def _json(payload: object) -> bytes:
    """Return the body a client would send for ``payload``."""
    return httpx.Request("POST", _ENCODE, json=payload).content


def _plain_application() -> FastAPI:
    app = FastAPI()

    @app.post("/form")
    async def form(
        title: Annotated[str, Form()], pages: Annotated[int, Form()]
    ) -> dict[str, object]:
        return {"title": title, "pages": pages}

    @app.post("/file-and-form")
    async def file_and_form(
        note: Annotated[str, Form()], doc: Annotated[UploadFile, File()]
    ) -> dict[str, object]:
        return {"note": note, "read": (await doc.read()).decode()}

    @app.post("/body")
    async def body(book: Book) -> dict[str, object]:
        return {"title": book.title, "pages": book.pages}

    @app.post("/embedded")
    async def embedded(book: Annotated[Book, Body(embed=True)]) -> dict[str, object]:
        return {"title": book.title, "pages": book.pages}

    @app.post("/json")
    async def json_body(payload: Annotated[dict[str, int], Body()]) -> dict[str, object]:
        return {"payload": payload}

    setup(app, message_kernel())
    return app


def _marked_application() -> FastAPI:
    """The same five routes, each also asking for the request as a message."""
    app = FastAPI()

    @app.post("/form")
    async def form(
        title: Annotated[str, Form()],
        pages: Annotated[int, Form()],
        message: Injected[ServerRequestInterface],
    ) -> dict[str, object]:
        del message
        return {"title": title, "pages": pages}

    @app.post("/file-and-form")
    async def file_and_form(
        note: Annotated[str, Form()],
        doc: Annotated[UploadFile, File()],
        message: Injected[ServerRequestInterface],
    ) -> dict[str, object]:
        del message
        return {"note": note, "read": (await doc.read()).decode()}

    @app.post("/body")
    async def body(book: Book, message: Injected[ServerRequestInterface]) -> dict[str, object]:
        del message
        return {"title": book.title, "pages": book.pages}

    @app.post("/embedded")
    async def embedded(
        book: Annotated[Book, Body(embed=True)], message: Injected[ServerRequestInterface]
    ) -> dict[str, object]:
        del message
        return {"title": book.title, "pages": book.pages}

    @app.post("/json")
    async def json_body(
        payload: Annotated[dict[str, int], Body()], message: Injected[ServerRequestInterface]
    ) -> dict[str, object]:
        del message
        return {"payload": payload}

    setup(app, message_kernel())
    return app


_FILE_BODY: Final = _multipart({"note": "keep"}, {"doc": ("a.txt", b"body", "text/plain")})
_FILE_ONLY: Final = _multipart({}, {"doc": ("a.txt", b"body", "text/plain")})
_NOTE_ONLY: Final = _multipart({"note": "keep"}, {})

_CASES: Final = [
    pytest.param(
        "/form", _urlencoded({"title": "dune", "pages": "412"}), _URLENCODED, 200, id="form-ok"
    ),
    pytest.param("/form", b"", _URLENCODED, 422, id="form-empty"),
    pytest.param("/form", _urlencoded({"title": "dune"}), _URLENCODED, 422, id="form-short"),
    pytest.param(
        "/form", _urlencoded({"title": "dune", "pages": "many"}), _URLENCODED, 422, id="form-type"
    ),
    pytest.param("/file-and-form", _FILE_BODY, _MULTIPART, 200, id="file-ok"),
    pytest.param("/file-and-form", _FILE_ONLY, _MULTIPART, 422, id="file-no-note"),
    pytest.param("/file-and-form", _NOTE_ONLY, _MULTIPART, 422, id="file-no-file"),
    pytest.param("/body", _json({"title": "dune", "pages": 412}), _JSON, 200, id="body-ok"),
    pytest.param("/body", _json({}), _JSON, 422, id="body-empty"),
    pytest.param("/body", _json({"title": 1, "pages": "many"}), _JSON, 422, id="body-type"),
    pytest.param("/body", b"{", _JSON, 422, id="body-malformed"),
    pytest.param(
        "/embedded", _json({"book": {"title": "dune", "pages": 412}}), _JSON, 200, id="embedded-ok"
    ),
    pytest.param(
        "/embedded", _json({"title": "dune", "pages": 412}), _JSON, 422, id="embedded-flat"
    ),
    pytest.param("/embedded", _json({"book": {}}), _JSON, 422, id="embedded-short"),
    pytest.param("/json", _json({"a": 1}), _JSON, 200, id="json-ok"),
    pytest.param("/json", _json({"a": "x"}), _JSON, 422, id="json-type"),
    pytest.param("/json", _json([1, 2]), _JSON, 422, id="json-list"),
    pytest.param("/json", b"{", _JSON, 422, id="json-malformed"),
]


def _headers(response: httpx.Response) -> list[tuple[bytes, bytes]]:
    """Return the headers as they came off the wire, bar the one minted per request."""
    return [(name, value) for name, value in response.headers.raw if name.lower() != _REQUEST_ID]


async def _answer(
    app: FastAPI, path: str, body: bytes, media_type: str
) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    """Return the status, headers and body of posting ``body`` at ``path``."""
    async with serving(app) as client:
        response = await client.post(path, content=body, headers={"content-type": media_type})
    return response.status_code, _headers(response), response.content


@pytest.mark.parametrize(("path", "body", "media_type", "status"), _CASES)
async def test_the_answer_is_the_same_with_and_without_the_request_message(
    path: str, body: bytes, media_type: str, status: int
) -> None:
    plain = await _answer(_plain_application(), path, body, media_type)

    assert BUILT == []

    marked = await _answer(_marked_application(), path, body, media_type)
    built = list(BUILT)

    assert plain[0] == status
    assert marked == plain
    # A guard on the comparison: an accepted payload reaches the marker, so a
    # change that stopped the message being served would make these vacuous.
    # An accepted payload has a parsed side — a form, JSON — so the container
    # reads it before handing the message on: one read, through the very
    # request object the framework's own parsing caches on.
    if status == 200:
        assert built == [path]


async def test_the_published_schema_is_the_same_with_and_without_the_request_message() -> None:
    assert _marked_application().openapi() == _plain_application().openapi()
