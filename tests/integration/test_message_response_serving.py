"""The response a route is handed, and the ones it makes, going out as they are.

Nothing converts a response here and nothing configures one: the injected
response and every response the injected factory makes are already what the
framework sends, so a route writes a status, a header or a body into one and
returns it. What the lifecycle adds around it — the request id, the listeners
— still applies, and a background task the route queued still runs once the
answer has left.

The routes are also the typed shape an application writes: the parameter is
the bridge's own ``Response`` and so is the return annotation, with nothing
narrowing one to the other — which is what the type checker reading this
module proves.
"""

from __future__ import annotations

from typing import Final

import pytest
from fastapi import BackgroundTasks, FastAPI
from xtr_dependency_injection import Injected

# Read at runtime: the framework evaluates a route's annotations.
from xtr_http_message_contracts import ResponseInterface
from xtr_http_message_contracts.factory import StreamFactoryInterface

from tests.support.message_apps import message_kernel
from tests.support.serving import serving
from xtr_http_kernel import setup
from xtr_http_kernel.bridge import Response, ResponseFactory

pytestmark = pytest.mark.anyio

KINDS: Final[list[str]] = []
"""The class of every response the factory route made or changed."""

SEEN: Final[list[Response]] = []
"""The response handed to each request the identity route served."""

ORDER: Final[list[str]] = []
"""What happened around the background task, in order."""


@pytest.fixture(autouse=True)
def _clear_journals() -> None:
    KINDS.clear()
    SEEN.clear()
    ORDER.clear()


def _note(what: str) -> None:
    ORDER.append(what)


def _application() -> FastAPI:
    app = FastAPI()

    @app.post("/answer")
    async def answer(response: Injected[Response]) -> Response:
        _ = await response.get_body().write(b'{"id": 7}')
        return (
            response.with_status(201)
            .with_header("content-type", "application/json")
            .with_added_header("x-answer", "yes")
        )

    @app.get("/bare")
    async def bare(response: Injected[Response]) -> Response:
        _ = await response.get_body().write(b"plain")
        return response

    @app.get("/same")
    async def same(
        response: Injected[Response],
        contract: Injected[ResponseInterface],
    ) -> Response:
        SEEN.append(response)
        _ = await response.get_body().write(b"same" if response is contract else b"two")
        return response

    @app.get("/from-factory")
    async def from_factory(
        responses: Injected[ResponseFactory],
        streams: Injected[StreamFactoryInterface],
    ) -> Response:
        made = responses.create_response(202, "Taken")
        KINDS.extend(
            type(step).__name__
            for step in (
                made,
                made.with_status(203),
                made.with_protocol_version("2"),
                made.with_header("content-type", "text/plain"),
                made.with_added_header("x-made", "here"),
                made.without_header("x-made"),
                made.with_body(streams.create_stream(b"elsewhere")),
            )
        )
        return (
            made.with_status(203, "Nearly")
            .with_header("content-type", "text/plain")
            .with_body(streams.create_stream(b"made here"))
        )

    @app.get("/background")
    async def background(tasks: BackgroundTasks, response: Injected[Response]) -> Response:
        tasks.add_task(_note, "task")
        _ = await response.get_body().write(b"queued")
        return response

    setup(app, message_kernel())
    return app


async def test_the_injected_response_goes_out_as_the_route_left_it() -> None:
    async with serving(_application()) as client:
        response = await client.post("/answer")

    assert response.status_code == 201
    assert response.content == b'{"id": 7}'
    assert response.headers["content-type"] == "application/json"
    assert response.headers["x-answer"] == "yes"
    assert response.headers["content-length"] == "9"


async def test_a_response_carrying_no_header_is_sent_without_one_added() -> None:
    async with serving(_application()) as client:
        response = await client.get("/bare")

    assert response.status_code == 200
    assert response.content == b"plain"
    assert "content-type" not in response.headers


async def test_the_bridge_class_and_the_contract_hand_over_the_same_response() -> None:
    async with serving(_application()) as client:
        response = await client.get("/same")

    assert response.content == b"same"


async def test_each_request_is_answered_with_a_response_of_its_own() -> None:
    async with serving(_application()) as client:
        _ = await client.get("/same")
        _ = await client.get("/same")

    assert SEEN[0] is not SEEN[1]


async def test_every_response_the_factory_makes_and_changes_is_the_returnable_one() -> None:
    async with serving(_application()) as client:
        response = await client.get("/from-factory")

    assert set(KINDS) == {Response.__name__}
    assert len(KINDS) == 7
    assert response.status_code == 203
    assert response.content == b"made here"
    assert response.headers["content-type"] == "text/plain"


async def test_the_request_id_and_the_listeners_still_reach_it() -> None:
    async with serving(_application()) as client:
        response = await client.post("/answer")

    assert len(response.headers["x-request-id"]) == 32
    assert response.headers["x-stamped"] == "yes"


async def test_a_background_task_runs_once_the_answer_has_left() -> None:
    app = _application()

    async with serving(app, on_response_sent=lambda: _note("response sent")) as client:
        response = await client.get("/background")

    assert response.content == b"queued"
    assert ORDER == ["response sent", "task"]
