"""Routes declared by resource functions, on a real application, from ``setup()`` on."""

from __future__ import annotations

from typing import cast

import pytest
from fastapi import FastAPI
from xtr_dependency_injection import Kernel

from tests.support.bundles import TickBundle
from tests.support.serving import serving
from xtr_http_kernel import setup
from xtr_http_kernel.bundle import HttpKernelBundle

pytestmark = pytest.mark.anyio

_DECLARED = "tests.fixtures.routing.attribute_routes"
_INCLUDED = "tests.fixtures.routing.included_routes"


def _set_up(app: FastAPI, *resources: str) -> FastAPI:
    setup(
        app,
        Kernel(
            "xtr_http_kernel.bundle",
            env="test",
            bundles={HttpKernelBundle: {"all": True}, TickBundle: {"all": True}},
            resources=(_DECLARED, _INCLUDED, *resources),
        ),
    )
    return app


async def test_a_declared_route_is_served() -> None:
    async with serving(_set_up(FastAPI())) as client:
        answered = await client.get("/ping")

    assert answered.json() == {"ping": "pong"}


async def test_an_endpoint_injecting_a_service_gets_it_built_for_the_request() -> None:
    async with serving(_set_up(FastAPI())) as client:
        answered = await client.get("/ticks/7")

    body = cast("dict[str, object]", answered.json())
    assert answered.status_code == 200
    assert body["number"] == 7
    assert isinstance(body["tick"], str)
    assert body["tick"]


async def test_a_scoped_service_reaches_a_fresh_controller_per_request() -> None:
    async with serving(_set_up(FastAPI())) as client:
        first = cast("dict[str, object]", (await client.get("/ticks/1")).json())
        second = cast("dict[str, object]", (await client.get("/ticks/1")).json())

    # The tick is scoped, the controller transient: nothing survives a request.
    assert first["tick"] != second["tick"]


async def test_a_declared_path_parameter_validates() -> None:
    async with serving(_set_up(FastAPI())) as client:
        refused = await client.get("/ticks/abc")

    assert refused.status_code == 422


def test_the_api_description_documents_declared_routes() -> None:
    app = _set_up(FastAPI())

    paths = cast("dict[str, object]", app.openapi()["paths"])

    assert "/ticks/{number}" in paths
    assert "/ping" in paths


async def test_a_resource_of_its_own_is_served_where_it_declares() -> None:
    async with serving(_set_up(FastAPI())) as client:
        answered = await client.get("/books")

    assert answered.json() == {"books": "declared"}


async def test_a_group_under_its_prefix_answers_only_its_method() -> None:
    async with serving(_set_up(FastAPI())) as client:
        answered = await client.get("/shop/items")
        posted = await client.post("/shop/items")

    assert answered.json() == {"items": "many"}
    assert posted.status_code == 405


async def test_an_application_may_replace_the_controller_a_route_injects() -> None:
    async with serving(_set_up(FastAPI(), "tests.fixtures.routing.replaced_controller")) as client:
        answered = await client.get("/ticks/3")

    assert cast("dict[str, object]", answered.json())["tick"] == "replaced"
