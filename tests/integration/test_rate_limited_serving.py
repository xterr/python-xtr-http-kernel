"""A served application limiting routes, routers and itself through the rate limiter bundle."""

from __future__ import annotations

from typing import Annotated, cast

import pytest
from fastapi import APIRouter, FastAPI, Request
from xtr_dependency_injection import Kernel, Target
from xtr_rate_limiter import RateLimiterFactoryInterface

from tests.fixtures.rate_limited_app.listeners import REFUSED
from tests.support.serving import serving
from xtr_http_kernel import setup
from xtr_http_kernel.bundle import HttpKernelBundle
from xtr_http_kernel.exception import InvalidRateLimitError
from xtr_http_kernel.rate_limiter import RateLimited

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _clear_refusals() -> None:
    REFUSED.clear()


def _kernel() -> Kernel:
    return Kernel(
        "tests.fixtures.rate_limited_app",
        env="test",
        bundles={HttpKernelBundle: {"all": True}},
    )


def _by_user(request: Request) -> str:
    return request.headers.get("x-user", "anonymous")


async def _by_user_later(request: Request) -> str:
    return request.headers.get("x-user", "anonymous")


def _application() -> FastAPI:  # noqa: C901 — one application holding every kind of limit.
    app = FastAPI()

    @app.get("/decorated")
    @RateLimited("tight", expose_headers=True)
    async def decorated(page: int = 1) -> dict[str, int]:
        return {"page": page}

    @app.get("/books/{isbn}")
    @RateLimited("tight")
    async def book(isbn: str) -> dict[str, str]:
        return {"isbn": isbn}

    @app.get("/sync")
    @RateLimited("tight")
    def synchronous() -> dict[str, bool]:
        return {"sync": True}

    @app.get("/dependency", dependencies=[RateLimited("tight", key=_by_user)])
    async def dependency() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/writes")
    @RateLimited("tight", methods="post", key=_by_user_later)
    async def writes() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/writes")
    @RateLimited("tight", methods=["POST"])
    async def reads() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/stacked")
    @RateLimited("loose", expose_headers=True)
    @RateLimited("pair", tokens=2, expose_headers=True)
    async def stacked() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/quiet")
    @RateLimited("loose", expose_headers=True)
    @RateLimited("tight")
    async def quiet() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/unknown")
    @RateLimited("nowhere")
    async def unknown() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/bad-key")
    @RateLimited("tight", key=lambda _: 42)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
    async def bad_key() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/injected")
    async def injected(
        limiter: Annotated[RateLimiterFactoryInterface, Target("tight")],
    ) -> dict[str, bool]:
        return {"accepted": (await limiter.create("manual").consume()).is_accepted()}

    router = RateLimited("tight", key="router")(APIRouter(prefix="/router"))

    @router.get("/a")
    async def router_a() -> dict[str, str]:
        return {"route": "a"}

    @router.get("/b")
    async def router_b() -> dict[str, str]:
        return {"route": "b"}

    included = APIRouter(prefix="/included")

    @included.get("/c")
    async def included_c() -> dict[str, str]:
        return {"route": "c"}

    app.include_router(router)
    app.include_router(included, dependencies=[RateLimited("tight", key="included")])
    setup(app, _kernel())
    return app


async def test_a_decorated_route_is_limited_and_reports_its_limit() -> None:
    async with serving(_application()) as client:
        first = await client.get("/decorated", params={"page": 3})
        second = await client.get("/decorated")

    assert first.status_code == 200
    assert first.json() == {"page": 3}
    assert first.headers["x-ratelimit-limit"] == "1"
    assert first.headers["x-ratelimit-remaining"] == "0"
    assert int(first.headers["x-ratelimit-reset"]) > 0
    assert first.headers["cache-control"] == "private"
    assert second.status_code == 429
    assert int(second.headers["retry-after"]) in {59, 60}
    assert second.headers["x-ratelimit-remaining"] == "0"


async def test_a_refusal_is_dispatched_with_the_limiter_and_the_key() -> None:
    async with serving(_application()) as client:
        _ = await client.get("/dependency", headers={"x-user": "alice"})
        refused = await client.get("/dependency", headers={"x-user": "alice"})
        other = await client.get("/dependency", headers={"x-user": "bob"})

    assert refused.status_code == 429
    assert other.status_code == 200
    assert [(event.limiter_name, event.key) for event in REFUSED] == [("tight", "alice")]


async def test_another_path_parameter_does_not_earn_a_fresh_limit() -> None:
    async with serving(_application()) as client:
        first = await client.get("/books/1")
        second = await client.get("/books/2")

    assert (first.status_code, second.status_code) == (200, 429)
    assert REFUSED[0].key == "127.0.0.1~GET~/books/{isbn}"


async def test_a_synchronous_endpoint_is_limited_too() -> None:
    async with serving(_application()) as client:
        statuses = [(await client.get("/sync")).status_code for _ in range(2)]

    assert statuses == [200, 429]


async def test_only_the_limited_methods_count() -> None:
    async with serving(_application()) as client:
        reads = [(await client.get("/writes")).status_code for _ in range(3)]
        writes = [(await client.post("/writes")).status_code for _ in range(2)]

    assert reads == [200, 200, 200]
    assert writes == [200, 429]


async def test_a_router_limits_every_route_on_one_key() -> None:
    async with serving(_application()) as client:
        a = await client.get("/router/a")
        b = await client.get("/router/b")
        included = [(await client.get("/included/c")).status_code for _ in range(2)]

    assert (a.status_code, b.status_code) == (200, 429)
    assert included == [200, 429]


async def test_the_limit_closest_to_refusing_speaks_in_calls() -> None:
    async with serving(_application()) as client:
        first = await client.get("/stacked")
        second = await client.get("/stacked")
        third = await client.get("/stacked")

    # "pair" holds 4 tokens and each call takes 2: two calls in all.
    assert first.headers["x-ratelimit-limit"] == "2"
    assert first.headers["x-ratelimit-remaining"] == "1"
    assert second.headers["x-ratelimit-remaining"] == "0"
    assert third.status_code == 429


async def test_a_refusing_limit_that_keeps_quiet_leaves_no_headers() -> None:
    async with serving(_application()) as client:
        first = await client.get("/quiet")
        second = await client.get("/quiet")

    assert first.headers["x-ratelimit-limit"] == "5"
    assert second.status_code == 429
    assert "x-ratelimit-limit" not in second.headers


async def test_an_unknown_limiter_or_a_key_that_is_no_string_fails_the_request() -> None:
    async with serving(_application()) as client:
        unknown = await client.get("/unknown")
        bad_key = await client.get("/bad-key")

    assert unknown.status_code == 500
    assert bad_key.status_code == 500


async def test_a_limiter_is_injected_by_name() -> None:
    async with serving(_application()) as client:
        answers = [(await client.get("/injected")).json() for _ in range(2)]

    assert answers == [{"accepted": True}, {"accepted": False}]


async def test_the_limit_stays_out_of_the_published_schema() -> None:
    async with serving(_application()) as client:
        schema = cast(
            "dict[str, dict[str, dict[str, dict[str, list[dict[str, str]]]]]]",
            (await client.get("/openapi.json")).json(),
        )

    parameters = schema["paths"]["/decorated"]["get"]["parameters"]
    assert [parameter["name"] for parameter in parameters] == ["page"]


def test_a_router_with_routes_cannot_be_limited_after_the_fact() -> None:
    router = APIRouter()

    @router.get("/x")
    async def x() -> None: ...

    with pytest.raises(InvalidRateLimitError):
        _ = RateLimited("tight")(router)


def test_a_limit_takes_at_least_one_token() -> None:
    with pytest.raises(InvalidRateLimitError):
        _ = RateLimited("tight", tokens=0)
