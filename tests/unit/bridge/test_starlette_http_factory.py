"""Messages as the framework's own request and response: ported from the bridge's suite."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, cast

import pytest
from starlette.responses import StreamingResponse
from xtr_http_message import Response, ServerRequest, Stream
from xtr_http_message.factory import HttpFactory

from tests.support.asgi_requests import asgi_request
from tests.support.asgi_responses import body_of, sent
from tests.support.short_read_file import ShortReadFile
from xtr_http_kernel.bridge import HttpMessageFactory, StarletteHttpFactory
from xtr_http_kernel.exception import InvalidCookieError

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import BinaryIO

    from xtr_http_message_contracts import ServerRequestInterface

pytestmark = pytest.mark.anyio

_URI = "http://bookshop.test/about/ada?url=http%3A%2F%2Fbookshop.test"
_STUB = object()
_SERVED_COOKIES = b'sid=abc123; theme=light; prefs="a b"; sort=title,year'
"""A ``Cookie`` header of the shape a browser sends, quoted value and all."""


@pytest.fixture
def pipe() -> Iterator[BinaryIO]:
    """A readable body whose cursor cannot be moved: a pipe reads once, forward."""
    reading, writing = os.pipe()
    _ = os.write(writing, b"chunk")
    os.close(writing)
    opened = cast("BinaryIO", os.fdopen(reading, "rb"))
    yield opened
    opened.close()


@pytest.fixture
def factory() -> StarletteHttpFactory:
    return StarletteHttpFactory()


@pytest.fixture
def message() -> ServerRequestInterface:
    return (
        ServerRequest(
            "GET",
            _URI,
            {"X-Books": "1.0", "X-Data": ["a", "b"]},
            b"The body",
            "1.1",
            {"country": "France"},
        )
        .with_cookie_params({"city": "Lille"})
        .with_attribute("custom", _STUB)
    )


async def test_the_query_string_of_the_uri_is_what_the_request_reads_parameters_from(
    factory: StarletteHttpFactory, message: ServerRequestInterface
) -> None:
    request = await factory.create_request(message)

    assert request.query_params["url"] == "http://bookshop.test"


async def test_the_body_of_the_message_is_what_the_request_reads(
    factory: StarletteHttpFactory, message: ServerRequestInterface
) -> None:
    request = await factory.create_request(message)

    assert await request.body() == b"The body"


async def test_a_streamed_body_still_reads_whole(
    factory: StarletteHttpFactory, message: ServerRequestInterface
) -> None:
    request = await factory.create_request(message, streamed=True)

    assert await request.body() == b"The body"


async def test_a_streamed_body_arrives_a_chunk_at_a_time(
    message: ServerRequestInterface,
) -> None:
    request = await StarletteHttpFactory(4).create_request(message, streamed=True)

    assert [chunk async for chunk in request.stream()] == [b"The ", b"body", b""]


async def test_a_streamed_body_whose_cursor_cannot_be_moved_still_arrives(
    factory: StarletteHttpFactory, pipe: BinaryIO
) -> None:
    message = ServerRequest("POST", _URI).with_body(Stream.create(pipe))

    request = await factory.create_request(message, streamed=True)

    assert await request.body() == b"chunk"


async def test_a_body_that_cannot_be_read_arrives_as_no_body_at_all(
    factory: StarletteHttpFactory, pipe: BinaryIO
) -> None:
    body = Stream.create(pipe)
    await body.close()
    message = ServerRequest("POST", _URI).with_body(body)

    request = await factory.create_request(message)

    assert await request.body() == b""


async def test_every_header_of_the_message_is_a_header_of_the_request(
    factory: StarletteHttpFactory, message: ServerRequestInterface
) -> None:
    headers = (await factory.create_request(message)).headers

    assert (headers["x-books"], headers.getlist("x-data")) == ("1.0", ["a", "b"])


async def test_the_cookies_of_the_message_are_the_cookies_of_the_request(
    factory: StarletteHttpFactory, message: ServerRequestInterface
) -> None:
    request = await factory.create_request(message)

    assert request.cookies == {"city": "Lille"}


async def test_a_cookie_header_the_message_carries_is_left_as_it_is(
    factory: StarletteHttpFactory,
) -> None:
    message = ServerRequest("GET", _URI, {"Cookie": "city=Paris"}).with_cookie_params(
        {"city": "Lille"}
    )

    request = await factory.create_request(message)

    assert request.cookies == {"city": "Paris"}


async def test_the_cookies_a_served_request_came_with_read_the_same_once_sent_back(
    factory: StarletteHttpFactory,
) -> None:
    served = asgi_request(headers=[(b"host", b"a.test"), (b"cookie", _SERVED_COOKIES)])
    one = HttpFactory()
    message = await HttpMessageFactory(one, one, one, one, one).create_request(served)

    sent_back = await factory.create_request(message.without_header("cookie"))

    assert sent_back.cookies == served.cookies


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("abc123", id="letters-and-digits"),
        pytest.param("", id="nothing-at-all"),
        pytest.param("eyJhIjoxfQ==", id="the-padding-of-base64"),
        pytest.param("a b", id="a-space-between"),
        pytest.param("title,year", id="a-comma"),
        pytest.param('a"b', id="a-double-quote-between"),
        pytest.param("a\\b", id="a-backslash"),
    ],
)
async def test_a_cookie_the_framework_reads_back_unchanged_is_sent_as_it_is(
    factory: StarletteHttpFactory, value: str
) -> None:
    message = ServerRequest("GET", _URI).with_cookie_params({"pick": value})

    request = await factory.create_request(message)

    assert request.cookies == {"pick": value}


@pytest.mark.parametrize(
    ("name", "value"),
    [
        pytest.param("a b", "1", id="a-name-with-a-space"),
        pytest.param("a=b", "1", id="a-name-with-the-pair-separator"),
        pytest.param("a;b", "1", id="a-name-with-the-cookie-separator"),
        pytest.param("caf\u00e9", "1", id="a-name-beyond-ascii"),
        pytest.param("", "1", id="no-name-at-all"),
        pytest.param("pick", "x\r\nx-books: 9", id="a-value-with-a-line-break"),
        pytest.param("pick", "a\tb", id="a-value-with-a-control-character"),
        pytest.param("pick", "10\u20ac", id="a-value-beyond-latin-1"),
        pytest.param("pick", "caf\u00e9", id="a-value-beyond-ascii"),
        pytest.param("pick", '"abc"', id="a-value-the-framework-would-unquote"),
        pytest.param("pick", " abc", id="a-value-the-framework-would-strip-in-front"),
        pytest.param("pick", "abc ", id="a-value-the-framework-would-strip-behind"),
    ],
)
async def test_a_cookie_that_would_not_read_back_as_it_was_is_refused_by_name(
    factory: StarletteHttpFactory, name: str, value: str
) -> None:
    message = ServerRequest("GET", _URI).with_cookie_params({name: value})

    with pytest.raises(InvalidCookieError) as refusal:
        _ = await factory.create_request(message)

    assert refusal.value.name == name
    assert f'The "{name}" cookie' in str(refusal.value)


async def test_a_cookie_value_carrying_another_cookie_is_refused_rather_than_sent(
    factory: StarletteHttpFactory,
) -> None:
    message = ServerRequest("GET", _URI).with_cookie_params({"a": "1; admin=true"})

    with pytest.raises(InvalidCookieError) as refusal:
        _ = await factory.create_request(message)

    assert (refusal.value.name, isinstance(refusal.value, ValueError)) == ("a", True)


async def test_the_attributes_of_the_message_are_what_the_route_matched(
    factory: StarletteHttpFactory, message: ServerRequestInterface
) -> None:
    request = await factory.create_request(message)

    assert request.path_params["custom"] is _STUB


async def test_the_environment_parameters_stand_under_the_connection(
    factory: StarletteHttpFactory, message: ServerRequestInterface
) -> None:
    request = await factory.create_request(message)

    assert request.scope["country"] == "France"


async def test_what_the_message_says_is_laid_over_the_environment_parameters(
    factory: StarletteHttpFactory,
) -> None:
    message = ServerRequest("POST", _URI, None, None, "1.1", {"method": "GET"})

    request = await factory.create_request(message)

    assert request.method == "POST"


async def test_the_path_of_the_request_comes_from_the_uri(
    factory: StarletteHttpFactory, message: ServerRequestInterface
) -> None:
    request = await factory.create_request(message)

    assert request.url.path == "/about/ada"


async def test_the_address_of_the_request_comes_from_the_uri(
    factory: StarletteHttpFactory, message: ServerRequestInterface
) -> None:
    request = await factory.create_request(message)

    assert request.scope["server"] == ("bookshop.test", 80)


async def test_a_message_with_no_host_names_no_address(factory: StarletteHttpFactory) -> None:
    request = await factory.create_request(ServerRequest("GET", "/about"))

    assert request.scope["server"] is None


async def test_the_protocol_version_of_the_message_is_the_connections(
    factory: StarletteHttpFactory,
) -> None:
    message = ServerRequest("GET", _URI, None, None, "1.0")

    request = await factory.create_request(message)

    assert request.scope["http_version"] == "1.0"


async def test_a_parsed_body_does_not_travel_because_the_request_reads_the_body_itself(
    factory: StarletteHttpFactory,
) -> None:
    message = ServerRequest(
        "POST",
        _URI,
        {"Content-Type": "application/x-www-form-urlencoded"},
        b"baz=2",
    ).with_parsed_body({"url": "http://shelf.test"})

    request = await factory.create_request(message)

    assert dict(await request.form()) == {"baz": "2"}


@pytest.fixture
def response() -> Response:
    return Response(
        200,
        {
            "X-Books": "2.8",
            "Set-Cookie": [
                "theme=light",
                "ABC=AeD; Domain=shelf.test; Path=/shelf; Secure; HttpOnly; SameSite=Strict",
            ],
        },
        b"The response body",
        "1.0",
    )


async def test_a_response_message_carries_its_status_and_headers_over(
    factory: StarletteHttpFactory, response: Response
) -> None:
    sendable = await factory.create_response(response)

    assert (sendable.status_code, sendable.headers["x-books"]) == (200, "2.8")


async def test_the_body_of_a_response_message_is_the_body_sent(
    factory: StarletteHttpFactory, response: Response
) -> None:
    sendable = await factory.create_response(response)

    assert sendable.body == b"The response body"


async def test_a_body_that_cannot_be_read_is_sent_as_no_body_at_all(
    factory: StarletteHttpFactory, pipe: BinaryIO
) -> None:
    body = Stream.create(pipe)
    await body.close()

    sendable = await factory.create_response(Response().with_body(body))

    assert sendable.body == b""


async def test_each_cookie_of_a_response_message_stays_a_header_of_its_own(
    factory: StarletteHttpFactory, response: Response
) -> None:
    sendable = await factory.create_response(response)

    assert sendable.headers.getlist("set-cookie") == [
        "theme=light",
        "ABC=AeD; Domain=shelf.test; Path=/shelf; Secure; HttpOnly; SameSite=Strict",
    ]


async def test_the_length_of_the_body_is_declared_for_a_response_message(
    factory: StarletteHttpFactory, response: Response
) -> None:
    sendable = await factory.create_response(response)

    assert sendable.headers["content-length"] == "17"


async def test_a_length_the_response_message_declares_is_the_one_sent(
    factory: StarletteHttpFactory,
) -> None:
    response = Response(200, {"Content-Length": "4"}, b"The response body")

    sendable = await factory.create_response(response)

    assert sendable.headers["content-length"] == "4"


async def test_a_streamed_response_message_goes_out_in_chunks_with_no_length(
    response: Response,
) -> None:
    sendable = await StarletteHttpFactory(4).create_response(response, streamed=True)

    messages = await sent(sendable)

    assert isinstance(sendable, StreamingResponse)
    assert "content-length" not in sendable.headers
    assert body_of(messages) == b"The response body"


async def test_a_streamed_response_message_keeps_its_status_and_headers(
    factory: StarletteHttpFactory, response: Response
) -> None:
    messages = await sent(await factory.create_response(response, streamed=True))

    start = messages[0]

    assert (cast("int", start["status"]), (b"x-books", b"2.8") in start["headers"]) == (200, True)


async def test_a_streamed_body_as_long_as_a_chunk_ends_where_it_ends() -> None:
    response = Response(200, None, b"four")

    sendable = await StarletteHttpFactory(4).create_response(response, streamed=True)

    messages = await sent(sendable)

    assert body_of(messages) == b"four"


async def test_a_streamed_body_that_cannot_be_read_goes_out_empty(
    factory: StarletteHttpFactory, pipe: BinaryIO
) -> None:
    body = Stream.create(pipe)
    await body.close()
    response = Response().with_body(body)

    messages = await sent(await factory.create_response(response, streamed=True))

    assert body_of(messages) == b""


async def test_a_streamed_body_arriving_a_little_at_a_time_goes_out_whole(
    factory: StarletteHttpFactory,
) -> None:
    response = Response().with_body(Stream.create(ShortReadFile(b"firstsecond", 5)))

    messages = await sent(await factory.create_response(response, streamed=True))

    assert body_of(messages) == b"firstsecond"
