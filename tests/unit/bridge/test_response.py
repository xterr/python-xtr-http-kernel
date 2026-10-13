"""The response that is a message and what the framework sends, at once."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, cast

import pytest
from starlette.background import BackgroundTask
from starlette.responses import Response as StarletteResponse
from xtr_http_message import Stream
from xtr_http_message_contracts import ResponseInterface

from tests.support.asgi_responses import body_of, sent
from tests.support.short_read_file import ShortReadFile
from xtr_http_kernel.bridge import Response

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import BinaryIO

    from starlette.types import Message

pytestmark = pytest.mark.anyio


@pytest.fixture
def pipe() -> Iterator[BinaryIO]:
    """A readable body of unknown length: a pipe cannot say how long it is."""
    reading, writing = os.pipe()
    _ = os.write(writing, b"chunk")
    os.close(writing)
    opened = cast("BinaryIO", os.fdopen(reading, "rb"))
    yield opened
    opened.close()


def _length(start: Message) -> str | None:
    """Return the length the response start declares, if it declares one."""
    headers = cast("list[tuple[bytes, bytes]]", start["headers"])

    return next(
        (value.decode() for name, value in headers if name == b"content-length"),
        None,
    )


def test_a_response_is_a_response_message() -> None:
    assert ResponseInterface in Response.__mro__


def test_a_response_is_what_the_framework_sends() -> None:
    assert isinstance(Response(), StarletteResponse)


def test_a_response_takes_the_reason_phrase_recommended_for_its_status() -> None:
    assert Response(404).get_reason_phrase() == "Not Found"


def test_a_response_asked_for_no_phrase_carries_none() -> None:
    assert Response(404, "").get_reason_phrase() == ""


def test_a_response_carries_the_phrase_it_was_given() -> None:
    assert Response(404, "Nowhere").get_reason_phrase() == "Nowhere"


def test_setting_a_status_hands_back_another_of_these() -> None:
    changed = Response().with_status(201)

    assert isinstance(changed, Response)
    assert (changed.get_status_code(), changed.get_reason_phrase()) == (201, "Created")


def test_setting_a_status_leaves_the_response_it_was_asked_of_alone() -> None:
    response = Response()

    changed = response.with_status(201)

    assert (changed is not response, response.get_status_code()) == (True, 200)


def test_the_status_the_framework_reads_is_the_one_the_message_holds() -> None:
    assert Response().with_status(418).status_code == 418


def test_a_status_the_framework_writes_reaches_the_message() -> None:
    response = Response()

    response.status_code = 404

    assert (response.get_status_code(), response.get_reason_phrase()) == (404, "Not Found")


def test_setting_a_header_hands_back_another_of_these() -> None:
    changed = Response().with_header("x-books", "2")

    assert isinstance(changed, Response)
    assert changed.get_header("x-books") == ["2"]


def test_the_headers_the_framework_reads_are_the_ones_the_message_holds() -> None:
    response = Response().with_header("X-Books", "2")

    assert response.headers["x-books"] == "2"


def test_a_header_the_framework_writes_reaches_the_message() -> None:
    response = Response()

    response.headers["x-books"] = "2"

    assert response.get_header("x-books") == ["2"]


def test_a_header_the_framework_removes_leaves_the_message() -> None:
    response = Response().with_header("x-books", "2")

    del response.headers["x-books"]

    assert response.has_header("x-books") is False


def test_headers_the_framework_writes_wholesale_replace_the_messages() -> None:
    response = Response().with_header("x-books", "2")

    response.raw_headers = [(b"x-shelf", b"7")]

    assert (response.has_header("x-books"), response.get_header("x-shelf")) == (False, ["7"])


def test_a_cookie_the_framework_sets_reaches_the_message() -> None:
    response = Response()

    response.set_cookie("city", "Lille")

    assert "city=Lille" in response.get_header("set-cookie")[0]


def test_there_is_no_body_to_read_off_the_response() -> None:
    # Reading a body is awaited, so no property hands one back: a reader
    # looking the framework's way finds nothing, and get_body() is the way in.
    assert getattr(Response(), "body", None) is None


async def test_a_body_the_framework_writes_reaches_the_message() -> None:
    response = Response()

    response.body = b"assigned"

    assert await response.get_body().get_contents() == b"assigned"


async def test_an_empty_body_the_framework_writes_replaces_what_the_message_held() -> None:
    response = Response()
    _ = await response.get_body().write(b"written")

    # What the framework assigns a response whose status allows no body.
    response.body = b""

    assert await response.get_body().get_contents() == b""


def test_a_response_keeps_its_background_task_through_a_change() -> None:
    response = Response()
    response.background = BackgroundTask(lambda: None)

    assert response.with_header("x-books", "2").background is response.background


def test_a_change_that_changes_nothing_hands_the_same_response_back() -> None:
    response = Response()

    assert response.with_protocol_version("1.1") is response


def test_a_response_speaks_the_usual_version_of_the_protocol() -> None:
    assert Response().get_protocol_version() == "1.1"


def test_a_version_set_on_a_response_is_the_one_it_holds() -> None:
    assert Response().with_protocol_version("1.0").get_protocol_version() == "1.0"


def test_the_values_of_a_header_read_as_one_line() -> None:
    response = Response().with_header("x-books", ["one", "two"])

    assert response.get_header_line("x-books") == "one, two"


def test_a_value_added_to_a_header_goes_after_what_it_held() -> None:
    response = Response().with_header("x-books", "one").with_added_header("x-books", "two")

    assert isinstance(response, Response)
    assert response.get_header("x-books") == ["one", "two"]


def test_a_header_taken_off_is_gone() -> None:
    response = Response().with_header("x-books", "one").without_header("x-books")

    assert isinstance(response, Response)
    assert response.has_header("x-books") is False


def test_the_wire_view_handed_out_stays_the_one_the_framework_writes_to() -> None:
    response = Response()

    assert response.raw_headers is response.raw_headers


def test_the_wire_view_handed_out_is_still_the_one_it_writes_to_after_a_read() -> None:
    response = Response()

    view = response.raw_headers
    _ = response.get_status_code()

    assert response.raw_headers is view


def test_a_header_written_through_a_view_held_across_a_read_reaches_the_message() -> None:
    response = Response()
    view = response.headers

    view["a"] = "1"
    _ = response.get_status_code()
    view["b"] = "2"

    assert (response.get_header("a"), response.get_header("b")) == (["1"], ["2"])


def test_a_wire_pair_appended_to_a_view_held_across_a_read_reaches_the_message() -> None:
    response = Response()
    view = response.raw_headers

    view.append((b"a", b"1"))
    _ = response.get_status_code()
    view.append((b"b", b"2"))

    assert (response.get_header("a"), response.get_header("b")) == (["1"], ["2"])


def test_a_header_set_on_the_message_shows_up_in_a_view_already_handed_out() -> None:
    response = Response()
    view = response.headers

    view["a"] = "1"
    response.raw_headers = [(b"b", b"2")]

    assert (view.get("a"), view["b"]) == (None, "2")


def test_a_view_handed_out_before_a_body_was_set_still_writes_to_the_message() -> None:
    response = Response()
    view = response.headers

    view["a"] = "1"
    response.body = b"assigned"
    view["b"] = "2"

    assert (response.get_header("a"), response.get_header("b")) == (["1"], ["2"])


async def test_what_goes_out_is_the_status_the_message_holds_when_it_is_sent() -> None:
    response = Response()

    response.status_code = 201
    messages = await sent(response)

    assert messages[0]["status"] == 201


async def test_what_goes_out_are_the_headers_the_message_holds_when_it_is_sent() -> None:
    response = Response()

    response.headers["x-books"] = "2"
    messages = await sent(response)

    assert (b"x-books", b"2") in cast("list[object]", messages[0]["headers"])


async def test_a_body_written_after_the_response_was_made_is_the_body_sent() -> None:
    response = Response()

    _ = await response.get_body().write(b'{"id": 7}')
    messages = await sent(response)

    assert body_of(messages) == b'{"id": 7}'


async def test_the_length_of_a_body_of_known_length_is_declared() -> None:
    response = Response()
    _ = await response.get_body().write(b'{"id": 7}')

    messages = await sent(response)

    assert _length(messages[0]) == "9"


async def test_a_length_the_message_declares_is_the_only_one_sent() -> None:
    response = Response().with_header("content-length", "4")
    _ = await response.get_body().write(b'{"id": 7}')

    messages = await sent(response)

    assert _length(messages[0]) == "4"


async def test_a_response_whose_answer_is_its_status_declares_no_length() -> None:
    messages = await sent(Response(204))

    assert _length(messages[0]) is None


async def test_an_interim_response_declares_no_length() -> None:
    messages = await sent(Response(100))

    assert _length(messages[0]) is None


async def test_a_body_of_unknown_length_goes_out_with_no_length_declared(
    pipe: BinaryIO,
) -> None:
    response = Response().with_body(Stream.create(pipe))

    messages = await sent(response)

    assert (_length(messages[0]), body_of(messages)) == (None, b"chunk")


async def test_a_body_of_unknown_length_goes_out_in_chunks(pipe: BinaryIO) -> None:
    response = Response().with_body(Stream.create(pipe))

    messages = await sent(response)

    assert [message.get("more_body", False) for message in messages[1:]] == [True, False]


async def test_a_body_that_cannot_be_read_goes_out_empty() -> None:
    response = Response()
    await response.get_body().close()

    messages = await sent(response)

    assert body_of(messages) == b""


async def test_a_body_arriving_a_little_at_a_time_goes_out_whole() -> None:
    response = Response().with_body(Stream.create(ShortReadFile(b"firstsecond", 5)))

    messages = await sent(response)

    assert body_of(messages) == b"firstsecond"


async def test_the_background_task_runs_once_the_response_has_gone_out() -> None:
    ran: list[str] = []

    async def afterwards() -> None:
        ran.append("ran")

    response = Response()
    response.background = BackgroundTask(afterwards)

    _ = await sent(response)

    assert ran == ["ran"]


async def test_a_socket_being_refused_is_answered_in_its_own_message_kinds() -> None:
    messages = await sent(Response(403), connection="websocket")

    assert [cast("str", message["type"]) for message in messages] == [
        "websocket.http.response.start",
        "websocket.http.response.body",
    ]
