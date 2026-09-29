"""Unit tests for :class:`xtr_http_kernel.rate_limiter.RateLimited`, without a kernel."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, cast

import pytest
from fastapi import APIRouter

from xtr_http_kernel.exception import InvalidRateLimitError, UnknownRateLimiterError
from xtr_http_kernel.rate_limiter import RateLimited

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request

pytestmark = pytest.mark.anyio


def test_it_is_a_dependency_run_for_every_declaration() -> None:
    limit = RateLimited("api", tokens=2, methods=["get", "post"], expose_headers=True)

    assert limit.dependency is not None
    assert not limit.use_cache
    assert (limit.limiter, limit.tokens, limit.expose_headers) == ("api", 2, True)
    assert limit.methods == {"GET", "HEAD", "POST"}
    assert RateLimited("api", methods="delete").methods == {"DELETE"}


def test_it_refuses_fewer_than_one_token() -> None:
    with pytest.raises(InvalidRateLimitError, match="at least one token"):
        _ = RateLimited("api", tokens=0)


async def test_a_decorated_endpoint_gains_a_hidden_dependency_it_never_sees() -> None:
    async def endpoint(page: int, **extra: object) -> tuple[int, dict[str, object]]:
        return page, extra

    limit = RateLimited("api")
    decorated = RateLimited("other")(limit(endpoint))
    parameters = inspect.signature(decorated).parameters

    assert list(parameters) == ["page", "_xtr_rate_limit_0", "_xtr_rate_limit_1", "extra"]
    hidden: object = parameters["_xtr_rate_limit_0"].default  # pyright: ignore[reportAny] -- a parameter's default is untyped
    assert hidden is limit
    assert parameters["_xtr_rate_limit_0"].kind is inspect.Parameter.KEYWORD_ONLY
    assert await decorated(3, _xtr_rate_limit_0=None, _xtr_rate_limit_1=None, x=1) == (3, {"x": 1})


def test_a_synchronous_endpoint_stays_synchronous() -> None:
    def endpoint(page: int) -> int:
        return page

    decorated = RateLimited("api")(endpoint)

    assert not inspect.iscoroutinefunction(decorated)
    assert decorated(4, _xtr_rate_limit_0=None) == 4  # pyright: ignore[reportCallIssue]  # ty: ignore[unknown-argument]


def test_a_router_takes_the_limit_before_its_routes() -> None:
    limit = RateLimited("api")
    router = limit(APIRouter())

    @router.get("/x")
    async def x() -> None: ...

    assert router.dependencies == [limit]
    with pytest.raises(InvalidRateLimitError, match="before adding its routes"):
        _ = RateLimited("other")(router)


async def _enforce(limit: RateLimited, request: Request) -> None:
    dependency = cast("Callable[[Request], Awaitable[None]]", limit.dependency)
    await dependency(request)


async def test_a_method_not_limited_is_let_through(http_request: Request) -> None:
    await _enforce(RateLimited("api", methods="post"), http_request)


async def test_without_a_kernel_no_limiter_is_known(http_request: Request) -> None:
    with pytest.raises(UnknownRateLimiterError) as raised:
        await _enforce(RateLimited("api"), http_request)

    assert raised.value.limiter == "api"
    assert raised.value.available == ()
