"""Unit tests for :class:`xtr_http_kernel.bundle.HttpKernelBundle`."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest
from starlette.datastructures import FormData
from starlette.websockets import WebSocket
from xtr_dependency_injection.testing import assert_zero_config
from xtr_event_dispatcher.bundle import EventDispatcherBundle
from xtr_http_message.factory import HttpFactory
from xtr_http_message_contracts import ResponseInterface, UploadedFileInterface

from tests.support.asgi_requests import asgi_request, received
from xtr_http_kernel.bridge import HttpMessageFactory, Response, ResponseFactory
from xtr_http_kernel.bundle import HttpKernelBundle, HttpKernelConfig, _messages
from xtr_http_kernel.bundle._messages import register, response, server_request
from xtr_http_kernel.exception import UnsupportedConnectionError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.requests import Request
    from xtr_dependency_injection import ServiceConfigurator
    from xtr_http_message_contracts import ServerRequestInterface

pytestmark = pytest.mark.anyio

_BOUNDARY = "thinboundary"
_MULTIPART = f"multipart/form-data; boundary={_BOUNDARY}".encode()


@final
class _RecordingConfigurator:
    """A configurator recording only the aliases ``register`` contributes."""

    def __init__(self) -> None:
        self.aliases: list[tuple[type, type]] = []

    def set(self, target: object, /, **options: object) -> object:
        del target, options
        return self

    def instance(self, value: object, /, **options: object) -> object:
        del value, options
        return self

    def alias(self, alias: type, target: type, /, **options: object) -> None:
        del options
        self.aliases.append((alias, target))


def _form_body() -> bytes:
    """Return a multipart body with one file in it."""
    return (
        f"--{_BOUNDARY}\r\n"
        'Content-Disposition: form-data; name="f1"; filename="f1.txt"\r\n'
        "Content-Type: text/plain\r\n\r\n"
        f"F1\r\n--{_BOUNDARY}--\r\n"
    ).encode()


def _message_factory() -> HttpMessageFactory:
    one = HttpFactory()

    return HttpMessageFactory(one, one, one, ResponseFactory(), one)


def _serving(monkeypatch: pytest.MonkeyPatch, connection: object) -> None:
    """Make ``connection`` the one the request factory reads."""
    monkeypatch.setattr(_messages, "current_connection", lambda: connection)


async def _finished(building: AsyncIterator[ServerRequestInterface]) -> None:
    """Let the request's scope end, running what the factory does as it closes."""
    with pytest.raises(StopAsyncIteration):
        _ = await anext(building)


async def test_zero_config_boots_and_shuts_down() -> None:
    await assert_zero_config(HttpKernelBundle)


def test_the_bundle_is_named_and_carries_its_config() -> None:
    metadata = HttpKernelBundle.metadata()

    assert metadata.name == "http_kernel"
    assert metadata.config is HttpKernelConfig


def test_the_config_is_buildable_with_no_arguments() -> None:
    assert HttpKernelConfig() == HttpKernelConfig()


def test_the_bundle_requires_the_event_dispatcher_and_its_optional_peers() -> None:
    targets = {declaration.target for declaration in HttpKernelBundle.metadata().required}

    assert EventDispatcherBundle in targets
    assert "xtr_logging.bundle:LoggingBundle" in targets
    assert "xtr_console.bundle:ConsoleBundle" in targets


async def test_the_response_of_a_request_comes_from_the_response_factory() -> None:
    assert isinstance(response(ResponseFactory()), Response)


def test_the_response_of_a_request_is_reachable_by_the_bridge_class_too() -> None:
    services = _RecordingConfigurator()

    register(cast("ServiceConfigurator", cast("object", services)))

    assert (Response, ResponseInterface) in services.aliases


async def test_the_request_of_a_request_is_built_from_the_connection_being_served(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = asgi_request(method="POST", path="/books", body=b"Content")
    _serving(monkeypatch, request)

    building = server_request(_message_factory())
    message = await anext(building)
    await _finished(building)

    assert (message.get_method(), bytes(message.get_body())) == ("POST", b"Content")


async def test_the_request_is_built_once_for_the_whole_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _serving(monkeypatch, asgi_request())

    building = server_request(_message_factory())
    _ = await anext(building)

    with pytest.raises(StopAsyncIteration):
        _ = await anext(building)


def _socket() -> WebSocket:
    """Return the connection a socket route is served from."""
    return WebSocket(
        {"type": "websocket", "path": "/live", "headers": [], "query_string": b""},
        received(b""),
        _done,
    )


async def test_a_socket_being_served_has_no_request_to_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _serving(monkeypatch, _socket())

    with pytest.raises(UnsupportedConnectionError, match='a "websocket" connection'):
        _ = await anext(server_request(_message_factory()))


async def test_the_refusal_names_what_was_being_served_instead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _serving(monkeypatch, _socket())

    with pytest.raises(UnsupportedConnectionError) as refusal:
        _ = await anext(server_request(_message_factory()))

    assert refusal.value.connection == "websocket"


@pytest.fixture
def submitted(monkeypatch: pytest.MonkeyPatch) -> Request:
    request = asgi_request(
        method="POST",
        headers=[(b"host", b"a.test"), (b"content-type", _MULTIPART)],
        body=_form_body(),
    )
    _serving(monkeypatch, request)

    return request


async def test_a_submitted_file_is_readable_while_the_request_is_being_served(
    submitted: Request,
) -> None:
    del submitted
    building = server_request(_message_factory())
    message = await anext(building)

    one = cast("UploadedFileInterface", message.get_uploaded_files()["f1"])
    read = bytes(one.get_stream())
    await _finished(building)

    assert read == b"F1"


async def test_a_form_the_factory_parsed_is_closed_when_the_scope_ends(
    submitted: Request,
) -> None:
    del submitted
    building = server_request(_message_factory())
    message = await anext(building)

    await _finished(building)

    one = cast("UploadedFileInterface", message.get_uploaded_files()["f1"])
    assert one.get_stream().is_readable() is False


async def test_closing_a_form_a_second_time_costs_nothing(submitted: Request) -> None:
    building = server_request(_message_factory())
    message = await anext(building)

    await _finished(building)
    # What the framework does with a form it parsed itself.
    await cast("FormData", message.get_parsed_body()).close()
    await submitted.close()

    assert cast("FormData", message.get_parsed_body())["f1"] is not None


async def _done(message: object) -> None:
    """Swallow what a socket would have sent: nothing here reads it."""
    del message
