"""Bundles for the served-application tests.

``ServedBundle`` registers what the fixture application's routes reach for:
the greeting parameter, a qualified channel, and three middleware factories
tagged for the setup call to compose — registered lowest priority first, so
the order the tests observe can only come from sorting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_dependency_injection import Bundle, as_bundle

from xtr_http_kernel import MIDDLEWARE_TAG

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

__all__ = ["STAMPS_SCOPE_KEY", "Channel", "PlainStamp", "ServedBundle", "Stamp"]

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
    """A contributed middleware factory advertising its place with ``priority``."""

    def __init__(self, label: str, priority: int) -> None:
        self.label = label
        self.priority = priority

    def __call__(self, app: ASGIApp) -> ASGIApp:
        return _stamping(self.label, app)


@final
class PlainStamp:
    """A contributed middleware factory with no ``priority`` — the default 0."""

    label = "plain"

    def __call__(self, app: ASGIApp) -> ASGIApp:
        return _stamping(self.label, app)


def inner_stamp() -> Stamp:
    return Stamp("inner", priority=-5)


def outer_stamp() -> Stamp:
    return Stamp("outer", priority=10)


@final
class Channel:
    """A qualified service a route selects with a target marker."""

    def __init__(self, name: str) -> None:
        self.name = name


def smtp_channel() -> Channel:
    return Channel("smtp")


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
