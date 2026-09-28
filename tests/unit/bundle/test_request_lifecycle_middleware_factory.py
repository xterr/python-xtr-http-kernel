"""Unit tests for the middleware factory the bundle contributes."""

from __future__ import annotations

from xtr_event_dispatcher import EventDispatcher

from xtr_http_kernel import RequestLifecycleMiddleware
from xtr_http_kernel.bundle.request_lifecycle_middleware_factory import (
    RequestLifecycleMiddlewareFactory,
)


async def _app(scope: object, receive: object, send: object) -> None:
    del scope, receive, send


def test_it_advertises_its_place_with_a_priority_attribute() -> None:
    factory = RequestLifecycleMiddlewareFactory(EventDispatcher(), priority=7)

    assert factory.priority == 7


def test_the_priority_defaults_to_zero() -> None:
    factory = RequestLifecycleMiddlewareFactory(EventDispatcher())

    assert factory.priority == 0


def test_it_wraps_the_app_in_the_lifecycle_middleware() -> None:
    factory = RequestLifecycleMiddlewareFactory(EventDispatcher())

    wrapped = factory(_app)

    assert isinstance(wrapped, RequestLifecycleMiddleware)
