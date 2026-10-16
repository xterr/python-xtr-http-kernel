"""Unit tests for the middleware factory the bundle contributes."""

from __future__ import annotations

from xtr_event_dispatcher import EventDispatcher
from xtr_http_message import HttpFactory

from xtr_http_kernel import RequestLifecycleMiddleware
from xtr_http_kernel.bridge import HttpMessageFactory, ResponseFactory
from xtr_http_kernel.bundle.request_lifecycle_middleware_factory import (
    RequestLifecycleMiddlewareFactory,
)


def _messages() -> HttpMessageFactory:
    one = HttpFactory()
    return HttpMessageFactory(one, one, one, ResponseFactory(), one)


async def _app(scope: object, receive: object, send: object) -> None:
    del scope, receive, send


def test_it_carries_no_priority_of_its_own() -> None:
    factory = RequestLifecycleMiddlewareFactory(EventDispatcher(), _messages())

    assert not hasattr(factory, "priority")


def test_it_wraps_the_app_in_the_lifecycle_middleware() -> None:
    factory = RequestLifecycleMiddlewareFactory(EventDispatcher(), _messages())

    wrapped = factory(_app)

    assert isinstance(wrapped, RequestLifecycleMiddleware)
