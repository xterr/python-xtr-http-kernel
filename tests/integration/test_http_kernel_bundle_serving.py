"""A served application with the bundle listed: the listeners at work per request.

The test application registers no middleware of its own — the lifecycle
middleware arrives tagged from the bundle and the setup call composes it.
"""

from __future__ import annotations

import re
from typing import ClassVar

import pytest
from fastapi import FastAPI
from xtr_dependency_injection import Kernel
from xtr_logging_contracts import EXCEPTION_KEY, Level

from tests.fixtures.lifecycle_app import logging_config
from tests.support.serving import serving
from xtr_http_kernel import setup
from xtr_http_kernel.bundle import HttpKernelBundle

pytestmark = pytest.mark.anyio

HEX_32 = re.compile(r"^[0-9a-f]{32}$")


class TeapotError(RuntimeError):
    """An exception carrying the status it stands for."""

    status_code: ClassVar[int] = 418


@pytest.fixture(autouse=True)
def _clear_captured() -> None:
    logging_config.CAPTURED.clear()


def _kernel(*extra_resources: str) -> Kernel:
    return Kernel(
        "tests.fixtures.lifecycle_app",
        env="test",
        bundles={HttpKernelBundle: {"all": True}},
        resources=("tests.fixtures.lifecycle_app", *extra_resources),
    )


def _application(kernel: Kernel) -> FastAPI:
    app = FastAPI()

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"ping": "pong"}

    @app.get("/boom")
    async def boom() -> dict[str, str]:
        raise RuntimeError("boom")

    @app.get("/teapot")
    async def teapot() -> dict[str, str]:
        raise TeapotError("short and stout")

    setup(app, kernel)
    return app


async def test_setup_installs_the_lifecycle_middleware() -> None:
    app = _application(_kernel())

    async with serving(app) as client:
        response = await client.get("/ping")

    assert response.status_code == 200
    assert HEX_32.match(response.headers["x-request-id"])


async def test_a_valid_request_id_is_echoed() -> None:
    app = _application(_kernel())

    async with serving(app) as client:
        response = await client.get("/ping", headers={"X-Request-Id": "trace-1.A_b"})

    assert response.headers["x-request-id"] == "trace-1.A_b"


async def test_an_invalid_request_id_is_replaced() -> None:
    app = _application(_kernel())

    async with serving(app) as client:
        response = await client.get("/ping", headers={"X-Request-Id": "bad id!"})

    assert response.headers["x-request-id"] != "bad id!"
    assert HEX_32.match(response.headers["x-request-id"])


async def test_a_server_error_logs_one_critical_record_with_the_request_id() -> None:
    app = _application(_kernel())

    async with serving(app) as client:
        response = await client.get("/boom", headers={"X-Request-Id": "boom-1"})

    assert response.status_code == 500
    handler = logging_config.CAPTURED[-1]
    criticals = [record for record in handler.records if record.level is Level.CRITICAL]
    assert len(criticals) == 1
    assert isinstance(criticals[0].context[EXCEPTION_KEY], RuntimeError)
    assert criticals[0].extra["request_id"] == "boom-1"


async def test_a_client_error_status_logs_at_error_level() -> None:
    app = _application(_kernel())

    async with serving(app) as client:
        response = await client.get("/teapot")

    assert response.status_code == 500
    handler = logging_config.CAPTURED[-1]
    assert handler.has_records(Level.ERROR)
    assert not handler.has_records(Level.CRITICAL)


async def test_the_indexing_header_appears_only_when_enabled() -> None:
    app = _application(_kernel())
    async with serving(app) as client:
        plain = await client.get("/ping")

    marked_app = _application(_kernel("tests.fixtures.lifecycle_overrides.indexing"))
    async with serving(marked_app) as client:
        marked = await client.get("/ping")

    assert "x-robots-tag" not in plain.headers
    assert marked.headers["x-robots-tag"] == "noindex"
