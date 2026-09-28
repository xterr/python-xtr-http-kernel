"""The one middleware the setup call adds, driven directly as plain ASGI.

The class is private, so the tests take it from where setup registered it —
the application's middleware list — and build instances with their own scope
opener and downstream app.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast

import pytest
from fastapi import FastAPI
from xtr_dependency_injection import Kernel

from xtr_http_kernel import MiddlewareStack, setup

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable
    from contextlib import AbstractAsyncContextManager

    from starlette.types import ASGIApp, Message, Receive, Scope, Send

pytestmark = pytest.mark.anyio

_STACK_KEY = "_xtr_http_kernel_middleware"


class ScopeJournal:
    """A scope opener journalling every enter and exit."""

    def __init__(self) -> None:
        self.entries: list[str] = []

    def __call__(self, application: object) -> AbstractAsyncContextManager[None]:
        del application
        return self._open()

    @asynccontextmanager
    async def _open(self) -> AsyncGenerator[None, None]:
        self.entries.append("scope opened")
        try:
            yield
        finally:
            self.entries.append("scope closed")


def _kernel_middleware(downstream: ASGIApp, opener: ScopeJournal) -> ASGIApp:
    shell = FastAPI()
    setup(shell, Kernel("tests.fixtures.served_app", env="test", bundles={}))
    cls = cast("Callable[..., ASGIApp]", shell.user_middleware[0].cls)
    return cls(downstream, open_scope=opener)


def _downstream(journal: list[str]) -> ASGIApp:
    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        del scope, receive, send
        journal.append("downstream")

    return downstream


async def _receive() -> Message:
    return {"type": "http.request"}


async def _send(message: Message) -> None:
    del message


def _scope(kind: str, application: FastAPI) -> dict[str, object]:
    return {"type": kind, "app": application}


@pytest.mark.parametrize("kind", ["http", "websocket"])
async def test_a_request_runs_inside_the_scope(kind: str) -> None:
    opener = ScopeJournal()
    middleware = _kernel_middleware(_downstream(opener.entries), opener)

    await middleware(_scope(kind, FastAPI()), _receive, _send)

    assert opener.entries == ["scope opened", "downstream", "scope closed"]


async def test_the_lifespan_passes_through_without_a_scope() -> None:
    opener = ScopeJournal()
    middleware = _kernel_middleware(_downstream(opener.entries), opener)

    await middleware(_scope("lifespan", FastAPI()), _receive, _send)

    assert opener.entries == ["downstream"]


async def test_the_scope_closes_and_the_failure_propagates_when_downstream_raises() -> None:
    opener = ScopeJournal()

    async def failing(scope: Scope, receive: Receive, send: Send) -> None:
        del scope, receive, send
        raise RuntimeError("downstream failed")

    middleware = _kernel_middleware(failing, opener)

    with pytest.raises(RuntimeError, match="downstream failed"):
        await middleware(_scope("http", FastAPI()), _receive, _send)

    assert opener.entries == ["scope opened", "scope closed"]


def _labelling_factory(
    label: str, journal: list[str], wraps: list[str]
) -> Callable[[ASGIApp], ASGIApp]:
    def factory(app: ASGIApp) -> ASGIApp:
        wraps.append(label)

        async def labelled(scope: Scope, receive: Receive, send: Send) -> None:
            journal.append(label)
            await app(scope, receive, send)

        return labelled

    return factory


async def test_the_parked_stack_wraps_outermost_first() -> None:
    opener = ScopeJournal()
    middleware = _kernel_middleware(_downstream(opener.entries), opener)
    application = FastAPI()
    wraps: list[str] = []
    setattr(
        application.state,
        _STACK_KEY,
        MiddlewareStack(
            (
                _labelling_factory("outer", opener.entries, wraps),
                _labelling_factory("inner", opener.entries, wraps),
            )
        ),
    )

    await middleware(_scope("http", application), _receive, _send)

    assert opener.entries == ["scope opened", "outer", "inner", "downstream", "scope closed"]


async def test_the_chain_is_composed_once_per_stack() -> None:
    opener = ScopeJournal()
    middleware = _kernel_middleware(_downstream(opener.entries), opener)
    application = FastAPI()
    wraps: list[str] = []
    first = MiddlewareStack((_labelling_factory("first", opener.entries, wraps),))
    setattr(application.state, _STACK_KEY, first)

    await middleware(_scope("http", application), _receive, _send)
    await middleware(_scope("http", application), _receive, _send)
    assert wraps == ["first"]

    setattr(
        application.state,
        _STACK_KEY,
        MiddlewareStack((_labelling_factory("second", opener.entries, wraps),)),
    )
    await middleware(_scope("http", application), _receive, _send)
    assert wraps == ["first", "second"]
