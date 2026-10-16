"""Unit tests for :class:`xtr_http_kernel.bridge.served_connection.ServedConnection`."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from starlette.datastructures import FormData, UploadFile
from starlette.requests import Request
from xtr_dependency_injection.exception import FastapiIntegrationError
from xtr_http_message import HttpFactory, ServerRequest

from tests.support.asgi_requests import asgi_request, asgi_scope
from xtr_http_kernel.bridge import HttpMessageFactory, ResponseFactory, served_connection
from xtr_http_kernel.bridge.served_connection import (
    SERVED_REQUEST_SCOPE_KEY,
    served_connection_of,
    served_request_of,
)

if TYPE_CHECKING:
    from starlette.types import Message
    from xtr_http_message_contracts import UploadedFileInterface

pytestmark = pytest.mark.anyio

_BOUNDARY = "servedrequest"
_MULTIPART = f"multipart/form-data; boundary={_BOUNDARY}".encode()

_FORM_BODY = (
    f"--{_BOUNDARY}\r\n"
    'Content-Disposition: form-data; name="title"\r\n\r\n'
    "dune\r\n"
    f"--{_BOUNDARY}\r\n"
    'Content-Disposition: form-data; name="doc"; filename="a.txt"\r\n'
    "Content-Type: text/plain\r\n\r\n"
    "body\r\n"
    f"--{_BOUNDARY}--\r\n"
).encode()


def _messages() -> HttpMessageFactory:
    one = HttpFactory()
    return HttpMessageFactory(one, one, one, ResponseFactory(), one)


def _served(body: bytes = b"", content_type: bytes | None = None) -> tuple[ServerRequest, Request]:
    headers = [(b"host", b"bookshop.test")]
    if content_type is not None:
        headers.append((b"content-type", content_type))
    request = asgi_request(
        "POST",
        path="/books/978-0141439518",
        query=b"quantity=2",
        headers=headers,
        body=body,
    )
    return _messages().serve(request), request


def _connection_of(request: Request) -> served_connection.ServedConnection:
    """Return the connection parked on ``request``'s scope — the one serve built over."""
    connection = served_connection_of(request.scope)
    assert connection is not None

    return connection


def test_the_head_is_read_off_the_connection_without_touching_the_wire() -> None:
    reads: list[Message] = []

    async def receive() -> Message:
        message = {"type": "http.request", "body": b"never", "more_body": False}
        reads.append(message)
        return message

    request = Request(asgi_scope("GET", path="/books"), receive)
    served = _messages().serve(request)

    assert (served.get_method(), served.get_uri().get_path()) == ("GET", "/books")
    assert served.get_uri().get_query() == ""
    assert served.get_request_target() == "/books"
    assert served.get_protocol_version() == "1.1"
    assert dict(served.get_headers()) == {"host": ["bookshop.test"]}
    assert served.has_header("HOST")
    assert served.get_header("host") == ["bookshop.test"]
    assert served.get_header_line("host") == "bookshop.test"
    assert served.get_cookie_params() == {}
    assert not served.get_query_params()
    assert served.get_server_params()["method"] == "GET"
    assert reads == []


async def test_a_form_body_is_parsed_with_its_files_when_it_is_materialised() -> None:
    served, request = _served(_FORM_BODY, content_type=_MULTIPART)

    assert served.get_parsed_body() is None
    # The stream serves the raw wire bytes for a form, not the empty stream.
    assert await served.get_body().get_contents() == _FORM_BODY

    form = cast("FormData", served.get_parsed_body())
    assert form["title"] == "dune"

    doc = cast("UploadedFileInterface", served.get_uploaded_files()["doc"])
    assert (doc.get_client_filename(), doc.get_size()) == ("a.txt", 4)
    assert await doc.get_stream().get_contents() == b"body"

    await _connection_of(request).close()


def test_the_attributes_follow_the_route_as_it_fills_them() -> None:
    served, request = _served()
    scope = request.scope

    assert served.get_attributes() == {}
    assert served.get_attribute("isbn", "none") == "none"

    scope["path_params"] = {"isbn": "978-0141439518"}

    assert served.get_attributes() == {"isbn": "978-0141439518"}
    assert served.get_attribute("isbn") == "978-0141439518"


def test_the_connection_parks_itself_and_serves_the_one_message() -> None:
    served, request = _served()
    connection = _connection_of(request)

    assert request.scope[SERVED_REQUEST_SCOPE_KEY] is connection
    assert served_request_of(request.scope) is served
    assert served_request_of({}) is None

    # One request, one message: however many times the factory is asked.
    assert _messages().serve(request) is served


async def test_the_replay_hands_the_buffered_bytes_back_to_the_application() -> None:
    served, request = _served(b"drained")
    original = request.receive
    connection = _connection_of(request)

    # Nothing materialised: the original channel passes through untouched.
    assert await connection.replay(original) is original

    assert await served.get_body().get_contents() == b"drained"
    replay = await connection.replay(original)

    assert await replay() == {"type": "http.request", "body": b"drained", "more_body": False}
    # Then the original channel's end: the read drained it, so what it still
    # offers is the disconnect.
    assert await replay() == {"type": "http.disconnect"}


async def test_a_form_it_parsed_is_closed_exactly_once() -> None:
    served, request = _served(_FORM_BODY, content_type=_MULTIPART)
    connection = _connection_of(request)
    assert await served.get_body().get_contents() == _FORM_BODY
    form = cast("FormData", served.get_parsed_body())
    doc = cast("UploadFile", form["doc"])
    closes: list[bool] = []
    original = doc.file.close

    def counting() -> None:
        closes.append(doc.file.closed)
        original()

    doc.file.close = counting  # ty: ignore[missing-slot] — a test counting the closes

    try:
        await connection.close()
        await connection.close()

        assert closes == [False]
        assert doc.file.closed
    finally:
        # Give the file its own deallocator back: the counting closure would
        # run while it is being torn down, and its extra work is not ours.
        doc.file.close = original  # ty: ignore[missing-slot] — giving the file its own deallocator back


async def test_a_body_nobody_read_leaves_nothing_to_close() -> None:
    served, request = _served(_FORM_BODY, content_type=_MULTIPART)

    await _connection_of(request).close()

    assert served.get_parsed_body() is None


async def test_the_serving_request_is_preferred_when_one_is_being_served(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    framework_reads: list[Message] = []

    async def framework_receive() -> Message:
        framework_reads.append({"type": "http.request", "body": b"cached", "more_body": False})
        return framework_reads[-1]

    framework = Request(asgi_scope("POST", path="/routed"), framework_receive)
    served, _request = _served(b"own")
    monkeypatch.setattr(served_connection, "current_connection", lambda: framework)

    # The read goes through the framework's own request — its channel, not
    # the served request's.
    assert await served.get_body().get_contents() == b"cached"
    assert framework_reads


async def test_the_own_request_is_read_before_anything_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    served, _request = _served(b"own")
    monkeypatch.setattr(
        served_connection,
        "current_connection",
        lambda: (_ for _ in ()).throw(FastapiIntegrationError("no")),
    )

    # No connection is being served, so this message's own request reads.
    assert await served.get_body().get_contents() == b"own"
