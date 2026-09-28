"""The middleware stack: an ordered, immutable chain of factories."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_http_kernel import MiddlewareStack

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.types import ASGIApp, Message, Receive, Scope, Send

pytestmark = pytest.mark.anyio


def _labelling_factory(label: str, journal: list[str]) -> Callable[[ASGIApp], ASGIApp]:
    def factory(app: ASGIApp) -> ASGIApp:
        async def labelled(scope: Scope, receive: Receive, send: Send) -> None:
            journal.append(label)
            await app(scope, receive, send)

        return labelled

    return factory


async def _run(app: ASGIApp) -> None:
    async def receive() -> Message:
        return {"type": "http.request"}

    async def send(message: Message) -> None:
        del message

    await app({"type": "http"}, receive, send)


async def test_wrap_composes_the_first_factory_outermost() -> None:
    journal: list[str] = []
    stack = MiddlewareStack(
        (_labelling_factory("outer", journal), _labelling_factory("inner", journal))
    )

    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        del scope, receive, send
        journal.append("downstream")

    await _run(stack.wrap(downstream))

    assert journal == ["outer", "inner", "downstream"]


def test_an_empty_stack_wraps_nothing() -> None:
    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        del scope, receive, send

    assert MiddlewareStack().wrap(downstream) is downstream


def test_len_counts_the_factories() -> None:
    journal: list[str] = []

    assert len(MiddlewareStack()) == 0
    assert len(MiddlewareStack((_labelling_factory("one", journal),))) == 1


def test_iter_yields_the_factories_in_order() -> None:
    journal: list[str] = []
    first = _labelling_factory("first", journal)
    second = _labelling_factory("second", journal)

    assert list(MiddlewareStack((first, second))) == [first, second]
