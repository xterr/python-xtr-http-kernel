"""What the framework read, as a message: ported from the bridge's own suite."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from urllib.parse import unquote

import pytest
from starlette.datastructures import FormData, QueryParams
from starlette.responses import FileResponse, JSONResponse, Response, StreamingResponse
from xtr_http_message.factory import HttpFactory
from xtr_http_message_contracts import UploadedFileInterface, UploadError

from tests.support.asgi_requests import asgi_request
from xtr_http_kernel.bridge import HttpMessageFactory, ResponseFactory
from xtr_http_kernel.bridge import Response as KernelResponse
from xtr_http_kernel.exception import RangedResponseBodyError, StreamedResponseBodyError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence
    from pathlib import Path

    from xtr_http_message_contracts import ServerRequestInterface

pytestmark = pytest.mark.anyio

_BOUNDARY = "thinboundary"
_MULTIPART = f"multipart/form-data; boundary={_BOUNDARY}".encode()


def _multipart(parts: Sequence[tuple[str, str | None, bytes]]) -> bytes:
    """Return a multipart body of ``(name, file name or none, content)`` parts."""
    written = b""
    for name, filename, content in parts:
        disposition = f'form-data; name="{name}"'
        if filename is not None:
            disposition = f'{disposition}; filename="{filename}"'
        head = f"--{_BOUNDARY}\r\nContent-Disposition: {disposition}\r\n"
        if filename is not None:
            head = f"{head}Content-Type: text/plain\r\n"
        written += f"{head}\r\n".encode() + content + b"\r\n"

    return written + f"--{_BOUNDARY}--\r\n".encode()


def _one(files: object) -> UploadedFileInterface:
    """Return the single uploaded file ``files`` holds, for a test to read."""
    assert isinstance(files, UploadedFileInterface)

    return files


@pytest.fixture
def factory() -> HttpMessageFactory:
    # One implementation behind all five roles, as the bridge's own suite does.
    one = HttpFactory()

    return HttpMessageFactory(one, one, one, one, one)


@pytest.fixture
async def created(factory: HttpMessageFactory) -> ServerRequestInterface:
    request = asgi_request(
        method="POST",
        path="/books",
        query=b"bar[baz]=42&foo=1",
        headers=[
            (b"host", b"shelf.test"),
            (b"x-books", b"2.8"),
            (b" x-broken", b"abc"),
            (b"cookie", b"c1=foo; c2=bar"),
        ],
        body=b"Content",
    )
    # What routing records once a route has matched.
    request.scope["path_params"] = {"isbn": "0262510871"}

    return await factory.create_request(request)


async def test_the_body_is_what_the_framework_read(created: ServerRequestInterface) -> None:
    assert bytes(created.get_body()) == b"Content"


async def test_the_body_can_still_be_read_off_the_framework_request_afterwards(
    factory: HttpMessageFactory,
) -> None:
    request = asgi_request(body=b"Content")

    message = await factory.create_request(request)

    assert (bytes(message.get_body()), await request.body()) == (b"Content", b"Content")


async def test_the_query_parameters_are_the_frameworks_own_object(
    created: ServerRequestInterface,
) -> None:
    assert isinstance(created.get_query_params(), QueryParams)


async def test_a_bracketed_query_name_is_the_name_it_was_sent_as(
    created: ServerRequestInterface,
) -> None:
    params = created.get_query_params()

    assert (params["foo"], params["bar[baz]"]) == ("1", "42")


async def test_every_value_of_a_repeated_query_name_is_still_reachable(
    factory: HttpMessageFactory,
) -> None:
    message = await factory.create_request(asgi_request(query=b"a=1&a=2"))

    params = cast("QueryParams", message.get_query_params())

    assert (params["a"], params.getlist("a")) == ("2", ["1", "2"])


async def test_the_request_target_is_the_path_with_the_query_after_it(
    created: ServerRequestInterface,
) -> None:
    assert unquote(created.get_request_target()) == "/books?bar[baz]=42&foo=1"


async def test_the_method_is_the_one_the_framework_read(created: ServerRequestInterface) -> None:
    assert created.get_method() == "POST"


async def test_a_header_arrives_as_a_header(created: ServerRequestInterface) -> None:
    assert created.get_header("X-Books") == ["2.8"]


async def test_a_header_the_message_grammar_refuses_is_left_out(
    created: ServerRequestInterface,
) -> None:
    assert (created.has_header(" x-broken"), created.has_header("x-broken")) == (False, False)


async def test_a_header_sent_twice_keeps_both_values(factory: HttpMessageFactory) -> None:
    message = await factory.create_request(
        asgi_request(headers=[(b"host", b"a.test"), (b"x-tag", b"one"), (b"X-Tag", b"two")])
    )

    assert message.get_header("x-tag") == ["one", "two"]


async def test_the_host_header_is_not_doubled_by_the_one_the_uri_implies(
    created: ServerRequestInterface,
) -> None:
    assert created.get_header("host") == ["shelf.test"]


async def test_the_environment_parameters_are_the_connections_own_entries(
    created: ServerRequestInterface,
) -> None:
    params = created.get_server_params()

    assert (params["type"], params["method"], params["client"]) == (
        "http",
        "POST",
        ("127.0.0.1", 51234),
    )


async def test_the_environment_parameters_leave_out_the_frameworks_own_machinery(
    created: ServerRequestInterface,
) -> None:
    params = created.get_server_params()

    assert ("headers" in params, "path_params" in params) == (False, False)


async def test_the_attributes_are_what_the_matched_route_named(
    created: ServerRequestInterface,
) -> None:
    assert created.get_attributes() == {"isbn": "0262510871"}


async def test_the_cookies_are_the_ones_the_framework_read(
    created: ServerRequestInterface,
) -> None:
    assert created.get_cookie_params() == {"c1": "foo", "c2": "bar"}


async def test_the_uri_is_built_from_the_connections_components(
    created: ServerRequestInterface,
) -> None:
    uri = created.get_uri()

    assert (uri.get_scheme(), uri.get_host(), uri.get_path()) == ("http", "shelf.test", "/books")


async def test_the_protocol_version_comes_from_the_connection(
    created: ServerRequestInterface,
) -> None:
    assert created.get_protocol_version() == "1.1"


async def test_a_body_of_no_declared_kind_leaves_no_parsed_body(
    created: ServerRequestInterface,
) -> None:
    assert created.get_parsed_body() is None


@pytest.mark.parametrize(
    ("content_type", "body", "parsed"),
    [
        pytest.param(
            b"application/json",
            b'{"city":"Paris","country":"France"}',
            {"city": "Paris", "country": "France"},
            id="object",
        ),
        pytest.param(b"application/json", b"{}", {}, id="empty-object"),
        pytest.param(b"application/json", b'{"city":"Paris"', None, id="malformed"),
        pytest.param(b"application/json", b"[1, 2]", None, id="array"),
        pytest.param(b"application/json", b'"Paris"', None, id="string"),
        pytest.param(
            b"application/ld+json", b'{"@id":"/books/1"}', {"@id": "/books/1"}, id="suffix"
        ),
        pytest.param(b"application/json; charset=utf-8", b"{}", {}, id="with-parameters"),
    ],
)
async def test_a_json_body_is_the_parsed_body_only_where_it_describes_an_object(
    factory: HttpMessageFactory,
    content_type: bytes,
    body: bytes,
    parsed: object,
) -> None:
    message = await factory.create_request(
        asgi_request(
            method="POST",
            headers=[(b"host", b"a.test"), (b"content-type", content_type)],
            body=body,
        )
    )

    assert message.get_parsed_body() == parsed


async def test_a_submitted_form_is_the_parsed_body_as_the_framework_parsed_it(
    factory: HttpMessageFactory,
) -> None:
    message = await factory.create_request(
        asgi_request(
            method="POST",
            headers=[(b"host", b"a.test"), (b"content-type", b"application/x-www-form-urlencoded")],
            body=b"tag=linen&baz=2",
        )
    )

    assert isinstance(message.get_parsed_body(), FormData)


async def test_every_value_of_a_repeated_form_field_is_still_reachable(
    factory: HttpMessageFactory,
) -> None:
    message = await factory.create_request(
        asgi_request(
            method="POST",
            headers=[(b"host", b"a.test"), (b"content-type", b"application/x-www-form-urlencoded")],
            body=b"tag=one&tag=two",
        )
    )

    form = cast("FormData", message.get_parsed_body())

    assert (form["tag"], form.getlist("tag")) == ("two", ["one", "two"])


async def test_a_form_leaves_the_body_of_the_message_empty(factory: HttpMessageFactory) -> None:
    message = await factory.create_request(
        asgi_request(
            method="POST",
            headers=[(b"host", b"a.test"), (b"content-type", b"application/x-www-form-urlencoded")],
            body=b"baz=2",
        )
    )

    assert bytes(message.get_body()) == b""


@pytest.fixture
async def submitted(factory: HttpMessageFactory) -> AsyncIterator[ServerRequestInterface]:
    message = await factory.create_request(
        asgi_request(
            method="POST",
            headers=[(b"host", b"a.test"), (b"content-type", _MULTIPART)],
            body=_multipart(
                [
                    ("f1", "f1.txt", b"F1"),
                    ("docs", "f2.txt", b"F2"),
                    ("docs", "f3.txt", b"F3"),
                    ("empty", "", b""),
                    ("baz", None, b"2"),
                ]
            ),
        )
    )
    yield message
    # What the bundle's factory does when the request's scope ends.
    await cast("FormData", message.get_parsed_body()).close()


async def test_a_submitted_file_is_an_uploaded_file(submitted: ServerRequestInterface) -> None:
    one = _one(submitted.get_uploaded_files()["f1"])

    assert (
        bytes(one.get_stream()),
        one.get_client_filename(),
        one.get_client_media_type(),
        one.get_error(),
    ) == (b"F1", "f1.txt", "text/plain", UploadError.OK)


async def test_a_submitted_file_knows_how_big_it_is(submitted: ServerRequestInterface) -> None:
    assert _one(submitted.get_uploaded_files()["f1"]).get_size() == 2


async def test_a_field_submitted_twice_carries_both_files(
    submitted: ServerRequestInterface,
) -> None:
    both = submitted.get_uploaded_files()["docs"]

    assert isinstance(both, tuple)
    assert [bytes(_one(one).get_stream()) for one in cast("tuple[object, ...]", both)] == [
        b"F2",
        b"F3",
    ]


async def test_a_field_submitted_with_no_file_says_so(submitted: ServerRequestInterface) -> None:
    one = _one(submitted.get_uploaded_files()["empty"])

    assert (one.get_error(), one.get_size()) == (UploadError.NO_FILE, 0)


async def test_a_plain_field_is_no_uploaded_file(submitted: ServerRequestInterface) -> None:
    assert "baz" not in submitted.get_uploaded_files()


async def test_a_plain_field_is_in_the_parsed_body(submitted: ServerRequestInterface) -> None:
    assert cast("FormData", submitted.get_parsed_body())["baz"] == "2"


def test_a_response_arrives_as_a_message(factory: HttpMessageFactory) -> None:
    response = Response("Response content.", 202, {"x-books": "3.4", " x-broken-header": "abc"})
    response.set_cookie("city", "Lille", httponly=True)

    message = factory.create_response(response)

    assert (
        bytes(message.get_body()),
        message.get_status_code(),
        message.get_header("x-books"),
        message.has_header("x-broken-header"),
        len(message.get_header("set-cookie")),
    ) == (b"Response content.", 202, ["3.4"], False, 1)


def test_a_response_takes_the_reason_phrase_recommended_for_its_status(
    factory: HttpMessageFactory,
) -> None:
    assert factory.create_response(Response(status_code=404)).get_reason_phrase() == "Not Found"


def test_a_cookie_set_on_a_response_travels_as_the_header_it_is(
    factory: HttpMessageFactory,
) -> None:
    response = Response()
    response.set_cookie("city", "Lille", path="/", httponly=True)

    header = factory.create_response(response).get_header("set-cookie")[0]

    assert "city=Lille" in header
    assert "HttpOnly" in header


def test_a_json_response_arrives_as_the_bytes_it_rendered(factory: HttpMessageFactory) -> None:
    message = factory.create_response(JSONResponse({"city": "Paris"}))

    assert (bytes(message.get_body()), message.get_header_line("content-type")) == (
        b'{"city":"Paris"}',
        "application/json",
    )


def test_a_file_response_is_read_from_its_file(factory: HttpMessageFactory, tmp_path: Path) -> None:
    path = tmp_path / "binary.bin"
    _ = path.write_bytes(b"Binary")

    body = factory.create_response(FileResponse(path)).get_body()
    read = bytes(body)
    body.close()

    assert read == b"Binary"


def test_a_response_whose_body_is_a_stream_of_chunks_is_refused(
    factory: HttpMessageFactory,
) -> None:
    async def lines() -> AsyncIterator[bytes]:
        yield b"Line 1\n"
        yield b"Line 2\n"

    streamed = StreamingResponse(lines())

    with pytest.raises(StreamedResponseBodyError) as refusal:
        _ = factory.create_response(streamed)

    assert refusal.value.response == "StreamingResponse"
    assert "stream of chunks" in str(refusal.value)


def test_a_file_response_declaring_one_range_of_the_file_is_refused(
    factory: HttpMessageFactory, tmp_path: Path
) -> None:
    path = tmp_path / "binary.bin"
    _ = path.write_bytes(b"Binary")
    ranged = FileResponse(path, status_code=206, headers={"content-range": "bytes 0-1/6"})

    with pytest.raises(RangedResponseBodyError) as refusal:
        _ = factory.create_response(ranged)

    assert (refusal.value.response, refusal.value.content_range) == (
        "FileResponse",
        "bytes 0-1/6",
    )
    assert "the range being sent" in str(refusal.value)


def test_the_response_is_whatever_the_response_factory_builds() -> None:
    one = HttpFactory()
    factory = HttpMessageFactory(one, one, one, ResponseFactory(), one)

    assert isinstance(factory.create_response(Response(status_code=201)), KernelResponse)
