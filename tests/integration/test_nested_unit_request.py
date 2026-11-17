"""A unit of work opened inside a request: it shares the request, and leaves it open.

New work received while a request is served — a message handled through
``sync://`` — opens a unit of its own inside the request's. Asked for the
request, it is handed the one being served; what it never does is close that
request's form, and the files uploaded with it, while the request still reads
them.
"""

from __future__ import annotations

from typing import Final

import pytest
from fastapi import FastAPI
from starlette.datastructures import FormData, UploadFile
from xtr_dependency_injection import Injected, Kernel, current_unit_of_work, unit_of_work
from xtr_http_message_contracts import ServerRequestInterface

from tests.support.serving import serving
from xtr_http_kernel import setup
from xtr_http_kernel.bundle import HttpKernelBundle

pytestmark = pytest.mark.anyio

HELD: Final[list[UploadFile]] = []
"""The uploaded file the route read, for a test to inspect after the request."""

SHARED: Final[list[bool]] = []
"""Whether the nested unit was handed the very request the route was."""


@pytest.fixture(autouse=True)
def _clear() -> None:
    HELD.clear()
    SHARED.clear()


def _uploaded(request: ServerRequestInterface) -> UploadFile:
    form = request.get_parsed_body()
    assert isinstance(form, FormData)
    uploaded = form["doc"]
    assert isinstance(uploaded, UploadFile)
    return uploaded


def _application() -> FastAPI:
    app = FastAPI()

    @app.post("/upload")
    async def upload(request: Injected[ServerRequestInterface]) -> dict[str, object]:
        unit = current_unit_of_work()
        assert unit is not None
        async with unit_of_work(unit, join=False) as nested:
            SHARED.append(await nested.get(ServerRequestInterface) is request)
        uploaded = _uploaded(request)
        HELD.append(uploaded)
        return {"closed": uploaded.file.closed, "read": (await uploaded.read()).decode()}

    setup(
        app,
        Kernel(
            "tests.fixtures.lifecycle_app",
            env="test",
            bundles={HttpKernelBundle: {"all": True}},
        ),
    )
    return app


async def test_a_nested_unit_does_not_close_the_requests_uploads() -> None:
    async with serving(_application()) as client:
        answered = await client.post("/upload", files={"doc": ("a.txt", b"body", "text/plain")})

    assert answered.json() == {"closed": False, "read": "body"}
    assert SHARED == [True]


async def test_the_requests_own_unit_still_closes_its_uploads() -> None:
    async with serving(_application()) as client:
        _ = await client.post("/upload", files={"doc": ("a.txt", b"body", "text/plain")})

    assert HELD[0].file.closed
