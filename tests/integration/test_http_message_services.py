"""The bridge under the container: what each interface resolves to."""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel, ScopeFactoryInterface
from xtr_dependency_injection.exception import ContainerCompilationError
from xtr_http_message.factory import HttpFactory

# Read at runtime: the container fills the constructor parameter below.
from xtr_http_message_contracts import (
    MessageInterface,
    RequestInterface,
    ResponseInterface,
    ServerRequestInterface,
)
from xtr_http_message_contracts.factory import (
    RequestFactoryInterface,
    ResponseFactoryInterface,
    ServerRequestFactoryInterface,
    StreamFactoryInterface,
    UploadedFileFactoryInterface,
    UriFactoryInterface,
)

from tests.support.asgi_requests import asgi_request
from tests.support.bundles import RequestReaderBundle, ResponseHolderBundle
from xtr_http_kernel.bridge import (
    HttpMessageFactory,
    HttpMessageFactoryInterface,
    Response,
    ResponseFactory,
    StarletteHttpFactory,
    StarletteHttpFactoryInterface,
)
from xtr_http_kernel.bundle import HttpKernelBundle, _messages

pytestmark = pytest.mark.anyio

_MESSAGE_FACTORIES = (
    RequestFactoryInterface,
    ServerRequestFactoryInterface,
    StreamFactoryInterface,
    UploadedFileFactoryInterface,
    UriFactoryInterface,
)


def _kernel() -> Kernel:
    return Kernel(
        "xtr_http_kernel.bundle",
        env="test",
        bundles={HttpKernelBundle: {"all": True}},
        resources=(),
    )


def _kernel_with_a_reader() -> Kernel:
    return Kernel(
        "xtr_http_kernel.bundle",
        env="test",
        bundles={HttpKernelBundle: {"all": True}, RequestReaderBundle: {"all": True}},
        resources=(),
    )


def _kernel_with_a_holder() -> Kernel:
    return Kernel(
        "xtr_http_kernel.bundle",
        env="test",
        bundles={HttpKernelBundle: {"all": True}, ResponseHolderBundle: {"all": True}},
        resources=(),
    )


@pytest.mark.parametrize(
    "interface",
    [
        pytest.param(RequestFactoryInterface, id="requests"),
        pytest.param(ServerRequestFactoryInterface, id="server-requests"),
        pytest.param(StreamFactoryInterface, id="streams"),
        pytest.param(UploadedFileFactoryInterface, id="uploaded-files"),
        pytest.param(UriFactoryInterface, id="uris"),
    ],
)
async def test_every_part_of_a_message_is_built_by_the_one_implementation(
    interface: type[object],
) -> None:
    async with await _kernel().boot() as booted:
        assert isinstance(await booted.container.get(interface), HttpFactory)


@pytest.mark.parametrize(
    ("interface", "implementation"),
    [
        pytest.param(ResponseFactoryInterface, ResponseFactory, id="responses"),
        pytest.param(HttpMessageFactoryInterface, HttpMessageFactory, id="messages"),
        pytest.param(StarletteHttpFactoryInterface, StarletteHttpFactory, id="framework"),
    ],
)
async def test_each_bridge_interface_resolves_to_its_implementation(
    interface: type[object], implementation: type[object]
) -> None:
    async with await _kernel().boot() as booted:
        assert isinstance(await booted.container.get(interface), implementation)


@pytest.mark.parametrize(
    "interface",
    [
        pytest.param(ServerRequestInterface, id="server-request"),
        pytest.param(RequestInterface, id="request"),
        pytest.param(MessageInterface, id="message"),
        pytest.param(ResponseInterface, id="response"),
        pytest.param(Response, id="kernel-response"),
    ],
)
async def test_the_request_and_the_response_of_a_request_are_registered(
    interface: type[object],
) -> None:
    async with await _kernel().boot() as booted:
        assert booted.container.has(interface)


@pytest.mark.parametrize(
    "interface",
    [
        pytest.param(ServerRequestInterface, id="server-request"),
        pytest.param(RequestInterface, id="request"),
        pytest.param(MessageInterface, id="message"),
    ],
)
async def test_every_interface_a_request_satisfies_leads_to_the_same_request(
    interface: type[object], monkeypatch: pytest.MonkeyPatch
) -> None:
    request = asgi_request(path="/books")
    monkeypatch.setattr(_messages, "current_connection", lambda: request)

    async with await _kernel().boot() as booted:
        scopes = await booted.container.get(ScopeFactoryInterface)
        async with scopes.unit_of_work(join=False) as unit:
            resolved: object = await unit.get(interface)
            again = await unit.get(ServerRequestInterface)

        assert resolved is again


async def test_the_response_of_a_request_is_one_an_endpoint_can_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = asgi_request()
    monkeypatch.setattr(_messages, "current_connection", lambda: request)

    async with await _kernel().boot() as booted:
        scopes = await booted.container.get(ScopeFactoryInterface)
        async with scopes.unit_of_work(join=False) as unit:
            assert isinstance(await unit.get(ResponseInterface), Response)


async def test_the_response_class_and_the_contract_lead_to_the_same_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = asgi_request()
    monkeypatch.setattr(_messages, "current_connection", lambda: request)

    async with await _kernel().boot() as booted:
        scopes = await booted.container.get(ScopeFactoryInterface)
        async with scopes.unit_of_work(join=False) as unit:
            by_class = await unit.get(Response)
            by_contract = await unit.get(ResponseInterface)

        assert by_class is by_contract


async def test_each_request_is_answered_with_a_response_of_its_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = asgi_request()
    monkeypatch.setattr(_messages, "current_connection", lambda: request)

    async with await _kernel().boot() as booted:
        scopes = await booted.container.get(ScopeFactoryInterface)
        async with scopes.unit_of_work(join=False) as first:
            one = await first.get(Response)
        async with scopes.unit_of_work(join=False) as second:
            another = await second.get(Response)

        assert one is not another


async def test_a_service_built_for_the_application_may_not_ask_for_one_request() -> None:
    kernel = _kernel_with_a_reader()

    with pytest.raises(ContainerCompilationError, match="Singletons can only depend on"):
        _ = await kernel.boot()


async def test_a_service_built_for_the_application_may_not_ask_for_one_response() -> None:
    kernel = _kernel_with_a_holder()

    with pytest.raises(ContainerCompilationError, match="Singletons can only depend on"):
        _ = await kernel.boot()
