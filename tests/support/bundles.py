"""Bundles for the served-application tests.

``ServedBundle`` registers what the fixture application's routes reach for:
the greeting parameter, a qualified channel, and three middleware factories
tagged for the http_kernel bundle to order — registered lowest tag priority
first, so the order the tests observe can only come from sorting.

``RequestReaderBundle`` registers the one service a request message must not
be injected into: one built for the application's whole life.

``ResponseHolderBundle`` is its counterpart for the response: the bridge's own
response class is as much one request's as the request message is, so a
service built for the application's life may not take it either.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_dependency_injection import Bundle, as_bundle

# Read at runtime: the container fills the constructor parameter below.
from xtr_http_message_contracts import ServerRequestInterface

from xtr_http_kernel import MIDDLEWARE_TAG
from xtr_http_kernel.bridge import Response  # noqa: TC001 — read at runtime, as above

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

__all__ = [
    "STAMPS_SCOPE_KEY",
    "Channel",
    "PlainStamp",
    "RequestReader",
    "RequestReaderBundle",
    "ResponseHolder",
    "ResponseHolderBundle",
    "ServedBundle",
    "Stamp",
]

STAMPS_SCOPE_KEY = "xtr_test_stamps"
"""Where the stamp middlewares journal the order the chain ran them in."""


def _stamping(label: str, app: ASGIApp) -> ASGIApp:
    async def stamped(scope: Scope, receive: Receive, send: Send) -> None:
        if cast("str", scope["type"]) == "http":
            cast("list[str]", scope.setdefault(STAMPS_SCOPE_KEY, [])).append(label)
        await app(scope, receive, send)

    return stamped


@final
class Stamp:
    """A contributed middleware factory; its place comes from its tag's ``priority``."""

    def __init__(self, label: str) -> None:
        self.label = label

    def __call__(self, app: ASGIApp) -> ASGIApp:
        return _stamping(self.label, app)


@final
class PlainStamp:
    """A contributed middleware factory tagged without a ``priority`` — the default 0."""

    label = "plain"

    def __call__(self, app: ASGIApp) -> ASGIApp:
        return _stamping(self.label, app)


def inner_stamp() -> Stamp:
    return Stamp("inner")


def outer_stamp() -> Stamp:
    return Stamp("outer")


@final
class Channel:
    """A qualified service a route selects with a target marker."""

    def __init__(self, name: str) -> None:
        self.name = name


def smtp_channel() -> Channel:
    return Channel("smtp")


@final
class RequestReader:
    """A service built for the application's life that asks for one request."""

    def __init__(self, request: ServerRequestInterface) -> None:
        self.request: ServerRequestInterface = request


@as_bundle("request_reader")
class RequestReaderBundle(Bundle[object]):
    """Registers the one service a request message must not be injected into."""

    @override
    def load_extension(
        self, config: object, services: ServiceConfigurator, builder: ContainerBuilder
    ) -> None:
        """Register the service, with the lifetime of the application."""
        del config, builder
        _ = services.set(RequestReader)


@final
class ResponseHolder:
    """A service built for the application's life that asks for one response."""

    def __init__(self, response: Response) -> None:
        self.response: Response = response


@as_bundle("response_holder")
class ResponseHolderBundle(Bundle[object]):
    """Registers the one service the response of a request must not be injected into."""

    @override
    def load_extension(
        self, config: object, services: ServiceConfigurator, builder: ContainerBuilder
    ) -> None:
        """Register the service, with the lifetime of the application."""
        del config, builder
        _ = services.set(ResponseHolder)


@as_bundle("served")
class ServedBundle(Bundle):
    """Registers what the fixture application's routes inject."""

    @override
    def load_extension(
        self, config: object, services: ServiceConfigurator, builder: ContainerBuilder
    ) -> None:
        del config
        builder.set_parameter("served.punctuation", "!")
        _ = services.set(smtp_channel, qualifier="smtp")
        _ = services.set(inner_stamp, qualifier="inner").add_tag(MIDDLEWARE_TAG, priority=-5)
        _ = services.set(PlainStamp).add_tag(MIDDLEWARE_TAG)
        _ = services.set(outer_stamp, qualifier="outer").add_tag(MIDDLEWARE_TAG, priority=10)
