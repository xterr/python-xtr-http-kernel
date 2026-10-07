"""The stack the bundle builds: tagged factories ordered when the kernel is compiled."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_dependency_injection import Bundle, Kernel, as_bundle

from tests.support.bundles import Stamp
from xtr_http_kernel import MIDDLEWARE_TAG, MiddlewareStack
from xtr_http_kernel.bundle import HttpKernelBundle
from xtr_http_kernel.exception import InvalidMiddlewarePriorityError
from xtr_http_kernel.request_lifecycle_middleware import RequestLifecycleMiddleware

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

pytestmark = pytest.mark.anyio

COMPOSED: list[str] = []
"""Every label the stack under test composed, innermost first."""


@final
class _ComposedStamp:
    """A contributed factory journalling its label when a stack composes it.

    ``wrap`` works inwards out, so the journal read backwards is the order
    the chain hands a request on in — outermost first.
    """

    def __init__(self, label: str) -> None:
        self._label = label

    def __call__(self, app: ASGIApp) -> ASGIApp:
        COMPOSED.append(self._label)
        return app


async def _passthrough(scope: Scope, receive: Receive, send: Send) -> None:
    """The application a stack is composed over, to see what it wrapped it in."""
    del scope, receive, send


def _composition_order(stack: MiddlewareStack) -> list[str]:
    """Compose ``stack`` over nothing and return the labels, outermost first."""
    COMPOSED.clear()
    _ = stack.wrap(_passthrough)
    return list(reversed(COMPOSED))


def low_stamp() -> _ComposedStamp:
    return _ComposedStamp("low")


def high_stamp() -> _ComposedStamp:
    return _ComposedStamp("high")


def tied_first_stamp() -> _ComposedStamp:
    return _ComposedStamp("tied-first")


def tied_second_stamp() -> _ComposedStamp:
    return _ComposedStamp("tied-second")


def default_stamp() -> _ComposedStamp:
    return _ComposedStamp("default")


def zero_stamp() -> _ComposedStamp:
    return _ComposedStamp("zero")


def bad_stamp() -> Stamp:
    return Stamp("bad")


@as_bundle("ordered")
class OrderedBundle(Bundle):
    """Tags stamps lowest priority first, so order can only come from sorting."""

    @override
    def load_extension(
        self, config: object, services: ServiceConfigurator, builder: ContainerBuilder
    ) -> None:
        del config, builder
        _ = services.set(low_stamp, qualifier="low").add_tag(MIDDLEWARE_TAG, priority=-5)
        _ = services.set(high_stamp, qualifier="high").add_tag(MIDDLEWARE_TAG, priority=50)
        _ = services.set(tied_first_stamp, qualifier="tied-first").add_tag(
            MIDDLEWARE_TAG, priority=3
        )
        _ = services.set(tied_second_stamp, qualifier="tied-second").add_tag(
            MIDDLEWARE_TAG, priority=3
        )
        _ = services.set(default_stamp, qualifier="default").add_tag(MIDDLEWARE_TAG)
        _ = services.set(zero_stamp, qualifier="zero").add_tag(MIDDLEWARE_TAG, priority=0)


@as_bundle("bad_priority")
class BadPriorityBundle(Bundle):
    """Tags one stamp with a priority no integer can be read from."""

    @override
    def load_extension(
        self, config: object, services: ServiceConfigurator, builder: ContainerBuilder
    ) -> None:
        del config, builder
        _ = services.set(bad_stamp, qualifier="bad").add_tag(MIDDLEWARE_TAG, priority="high")


def _kernel(contributor: type[Bundle]) -> Kernel:
    return Kernel(
        "xtr_http_kernel.bundle",
        env="test",
        bundles={contributor: {"all": True}, HttpKernelBundle: {"all": True}},
        resources=(),
    )


async def test_tag_priorities_order_the_stack_highest_outermost() -> None:
    async with await _kernel(OrderedBundle).boot() as booted:
        stack = await booted.container.get(MiddlewareStack)

    labels = _composition_order(stack)
    # ``low`` registered first yet sits last; the tied pair keeps its
    # registration order; ``default`` (no priority attribute) sits at 0 —
    # tied with the explicit ``zero`` registered after it, and before it.
    assert labels == ["high", "tied-first", "tied-second", "default", "zero", "low"]


async def test_the_bundle_alone_stacks_its_lifecycle_middleware() -> None:
    kernel = Kernel(
        "xtr_http_kernel.bundle",
        env="test",
        bundles={HttpKernelBundle: {"all": True}},
        resources=(),
    )

    async with await kernel.boot() as booted:
        stack = await booted.container.get(MiddlewareStack)

    assert isinstance(stack.wrap(_passthrough), RequestLifecycleMiddleware)


def test_a_non_integer_priority_fails_the_build_naming_the_service() -> None:
    with pytest.raises(InvalidMiddlewarePriorityError, match=r"Stamp\['bad'\].*'high'"):
        _ = _kernel(BadPriorityBundle).build()


def test_the_report_lists_the_middleware_stack_definition() -> None:
    compiled = _kernel(OrderedBundle).build()

    keys = [definition.key for definition in compiled.report.definitions]
    assert (MiddlewareStack, None) in keys
