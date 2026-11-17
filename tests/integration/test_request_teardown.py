"""A request whose scoped service fails to close: where the failure goes, served in-process."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from xtr_dependency_injection import Injected, Kernel

from tests.fixtures.teardown_app.services import ANSWER_FAILURES, Fragile
from tests.support.asgi_requests import asgi_scope
from tests.support.serving import driving
from xtr_http_kernel import setup
from xtr_http_kernel.bundle import HttpKernelBundle

if TYPE_CHECKING:
    from collections.abc import Iterator

    from starlette.types import Message

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _unanswered() -> Iterator[None]:
    ANSWER_FAILURES[0] = False
    yield
    ANSWER_FAILURES[0] = False


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/fails")
    async def fails(service: Injected[Fragile]) -> None:
        del service
        raise LookupError("the route failed")

    setup(
        app,
        Kernel(
            "tests.fixtures.teardown_app", env="test", bundles={HttpKernelBundle: {"all": True}}
        ),
    )
    return app


async def _receive() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}


def _close_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "xtr_dependency_injection" and record.levelno == logging.WARNING
    ]


async def test_an_unanswered_failure_carries_the_failed_cleanup_as_a_note(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="xtr_dependency_injection"):
        async with driving(_app()) as drive:
            with pytest.raises(LookupError) as raised:
                _ = await drive(asgi_scope(path="/fails"), _receive)

    assert raised.value.__notes__ == [
        "closing the unit's services also failed: RuntimeError('closing failed')"
    ]
    assert len(_close_warnings(caplog)) == 1


async def test_an_answered_failure_still_reports_the_failed_cleanup(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ANSWER_FAILURES[0] = True
    with caplog.at_level(logging.WARNING, logger="xtr_dependency_injection"):
        async with driving(_app()) as drive:
            with pytest.raises(ExceptionGroup):
                _ = await drive(asgi_scope(path="/fails"), _receive)

    (warning,) = _close_warnings(caplog)
    assert "RuntimeError('closing failed')" in warning
