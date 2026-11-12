"""A request reads and logs as itself, whatever context its task was started from.

A server gives no promise about the context a request's task starts with: on
a kept-alive connection it may be a copy of an earlier request's, taken once
that request had published its connection, opened its unit of work and bound
its log context. The same thing happens, with no server at all, when a route
starts a task that sends a request to the application it belongs to — the
task, and the request in it, begin with a copy of the first request's
context, mid-flight. That is how these tests start one request from another's.
"""

from __future__ import annotations

from typing import Annotated

import anyio
import httpx
import pytest
from fastapi import FastAPI, File, Form, UploadFile
from xtr_dependency_injection import Injected, Kernel
from xtr_logging import bind_context, current_context
from xtr_logging.bundle import LoggingBundle

from tests.fixtures.isolation_app.listeners import CUSTOMERS, READ, Reading
from tests.support.bundles import Tick, TickBundle
from tests.support.serving import serving
from xtr_http_kernel import setup
from xtr_http_kernel.bundle import HttpKernelBundle

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _forget_the_readings() -> None:
    READ.clear()
    CUSTOMERS.clear()


def _application(clients: list[httpx.AsyncClient]) -> FastAPI:
    """Return the application; ``clients`` holds the client its relay route sends through."""
    app = FastAPI()

    @app.post("/documents")
    async def documents(
        title: Annotated[str, Form()],
        doc: Annotated[UploadFile, File()],
        tick: Injected[Tick],
    ) -> dict[str, object]:
        del tick
        return {"title": title, "size": doc.size}

    @app.get("/plain")
    async def plain() -> dict[str, str]:
        return {"plain": "yes"}

    @app.post("/relay/{target}")
    async def relay(
        target: str,
        title: Annotated[str, Form()],
        tick: Injected[Tick],
    ) -> dict[str, object]:
        # This request's marker has resolved, so its connection is published
        # and its form is parsed, and its unit of work is open with a key
        # bound in it: the task started below begins with all of that.
        del title, tick
        bind_context({"customer": "outer"})
        answered: list[httpx.Response] = []

        async def send() -> None:
            if target == "documents":
                answered.append(
                    await clients[0].post(
                        "/documents",
                        data={"title": "inner"},
                        files={"doc": ("inner.txt", b"inner body", "text/plain")},
                    )
                )
            else:
                answered.append(await clients[0].get("/plain"))

        async with anyio.create_task_group() as tasks:
            _ = tasks.start_soon(send)
        started = answered[0]
        return {
            "status": started.status_code,
            "answer": started.json(),
            "customer": current_context().get("customer"),
        }

    setup(
        app,
        Kernel(
            "tests.fixtures.isolation_app",
            env="test",
            bundles={
                HttpKernelBundle: {"all": True},
                LoggingBundle: {"all": True},
                TickBundle: {"all": True},
            },
        ),
    )
    return app


async def test_a_request_started_from_anothers_context_reads_its_own_body() -> None:
    clients: list[httpx.AsyncClient] = []

    async with serving(_application(clients)) as client:
        clients.append(client)
        response = await client.post("/relay/documents", data={"title": "outer"})

    # The route behind the listener was handed the inner request's own bytes,
    # and the listener read the inner request's own form.
    assert response.json()["answer"] == {"title": "inner", "size": 10}
    assert list(READ) == [
        Reading("/relay/documents", None, "outer"),
        Reading("/documents", None, "inner"),
    ]


async def test_a_request_started_from_anothers_context_has_no_connection_until_its_own() -> None:
    clients: list[httpx.AsyncClient] = []

    async with serving(_application(clients)) as client:
        clients.append(client)
        response = await client.post("/relay/plain", data={"title": "outer"})

    assert response.json()["answer"] == {"plain": "yes"}
    # The inner route declared no marker, so nothing was ever published for
    # it: the outer request's connection is not its own.
    assert list(READ) == [Reading("/relay/plain", None, "outer"), Reading("/plain", None, None)]


async def test_a_request_started_from_anothers_context_does_not_log_under_its_keys() -> None:
    clients: list[httpx.AsyncClient] = []

    async with serving(_application(clients)) as client:
        clients.append(client)
        response = await client.post("/relay/plain", data={"title": "outer"})

    # The inner request arrived with the outer one's key in its context, and
    # found nothing bound once its own unit of work had begun.
    assert list(CUSTOMERS) == [None, None]
    # The outer request, back in its own unit, still logs under its key.
    assert response.json()["customer"] == "outer"
