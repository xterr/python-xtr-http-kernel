"""Thirty concurrent requests, each keeping its own log, uid and trace.

The application mixes an async and a sync (``def``) endpoint, half of the
requests logging a debug record and then raising. Per request the suite
asserts: a distinct ``X-Request-Id``; every batch the fingers-crossed
handler forwarded belongs to exactly one request; a quiet request forwards
nothing below the passthru floor; the uid is constant within a request —
the sync endpoint's worker-thread records included — and distinct across
requests; and a request's trace lists only its own events. A second
variant puts a queue handler in front of the fingers-crossed one, and a
console-style boot proves a process outside HTTP still logs on the
instance's state: one uid, one instance buffer.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

import anyio
import anyio.lowlevel
import pytest
from fastapi import FastAPI, Request
from xtr_dependency_injection import Injected, Kernel
from xtr_event_dispatcher import EventDispatcherInterface, GenericEvent
from xtr_event_dispatcher.bundle import EventDispatcherBundle
from xtr_logging.bundle import LoggingBundle
from xtr_logging_contracts import Level, LoggerInterface

from tests.fixtures.concurrent_app import services
from tests.support.serving import serving
from xtr_http_kernel import KernelEvents, setup
from xtr_http_kernel.bundle import HttpKernelBundle

if TYPE_CHECKING:
    import httpx
    from xtr_event_dispatcher.debug import TraceableEventDispatcher
    from xtr_logging import LogRecord

    from tests.fixtures.concurrent_app.services import CollectingHandler

pytestmark = pytest.mark.anyio

HEX_32 = re.compile(r"^[0-9a-f]{32}$")

_QUIET_ASYNC = 8
_QUIET_SYNC = 7
_BOOM_ASYNC = 8
_BOOM_SYNC = 7


@pytest.fixture(autouse=True)
def _clear_journals() -> None:
    services.COLLECTED.clear()
    services.UID_PROCESSORS.clear()


def _kernel(variant: str) -> Kernel:
    return Kernel(
        "tests.fixtures.concurrent_app",
        env="test",
        bundles={
            LoggingBundle: {"all": True},
            EventDispatcherBundle: {"all": True},
            HttpKernelBundle: {"all": True},
        },
        resources=(
            "tests.fixtures.concurrent_app.services",
            f"tests.fixtures.concurrent_app.{variant}",
        ),
        concurrent_scoped_access=True,
    )


def _application(kernel: Kernel) -> FastAPI:
    app = FastAPI()

    @app.get("/quiet/async")
    async def quiet_async(
        request: Request,
        dispatcher: Injected[EventDispatcherInterface],
        logger: Injected[LoggerInterface],
    ) -> dict[str, object]:
        request_id = cast("str", request.state.request_id)
        logger.debug("a quiet request passing through", {"path": request.url.path})
        first = services.UID_PROCESSORS[-1].uid
        await anyio.lowlevel.checkpoint()
        # A probe nobody listens to: the unit's trace must list it — and
        # only this request's own, however many probes fly concurrently.
        traced = cast("TraceableEventDispatcher", dispatcher)
        _ = await traced.dispatch(GenericEvent(request_id), f"probe.{request_id}")
        infos = traced.get_called_listeners()
        return {
            "request_id": request_id,
            "uids": [first, services.UID_PROCESSORS[-1].uid],
            "orphaned": traced.get_orphaned_events(),
            "events": sorted({info.event for info in infos}),
            "calls": [info.calls for info in infos],
        }

    @app.get("/quiet/sync")
    def quiet_sync(request: Request, logger: Injected[LoggerInterface]) -> dict[str, object]:
        # Runs in a copied context on a worker thread: the uid it reads
        # must still be the one this request's unit carries.
        logger.debug("a quiet request on a worker thread", {"path": request.url.path})
        first = services.UID_PROCESSORS[-1].uid
        second = services.UID_PROCESSORS[-1].uid
        return {"request_id": cast("str", request.state.request_id), "uids": [first, second]}

    @app.get("/boom/async")
    async def boom_async(request: Request, logger: Injected[LoggerInterface]) -> dict[str, object]:
        logger.debug("about to fail", {"path": request.url.path})
        raise RuntimeError(f"async boom {cast('str', request.state.request_id)}")

    @app.get("/boom/sync")
    def boom_sync(request: Request, logger: Injected[LoggerInterface]) -> dict[str, object]:
        logger.debug("about to fail on a worker thread", {"path": request.url.path})
        raise RuntimeError(f"sync boom {cast('str', request.state.request_id)}")

    setup(app, kernel)
    return app


async def _drive(
    client: httpx.AsyncClient,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[str]]:
    """Fire the thirty requests at once; return the quiet payloads and the boom ids."""
    quiet_async: list[dict[str, object]] = []
    quiet_sync: list[dict[str, object]] = []
    boom_ids = [f"boom-async-{n}" for n in range(_BOOM_ASYNC)] + [
        f"boom-sync-{n}" for n in range(_BOOM_SYNC)
    ]

    async def one_quiet(path: str, into: list[dict[str, object]]) -> None:
        response = await client.get(path)
        assert response.status_code == 200
        payload = cast("dict[str, object]", response.json())
        assert response.headers["x-request-id"] == payload["request_id"]
        into.append(payload)

    async def one_boom(path: str, request_id: str) -> None:
        # The 500 for an unanswered failure is the framework's own outermost
        # answer, past the lifecycle — so the id rides in with the request.
        response = await client.get(path, headers={"X-Request-Id": request_id})
        assert response.status_code == 500

    async with anyio.create_task_group() as group:
        for _ in range(_QUIET_ASYNC):
            _ = group.start_soon(one_quiet, "/quiet/async", quiet_async)
        for _ in range(_QUIET_SYNC):
            _ = group.start_soon(one_quiet, "/quiet/sync", quiet_sync)
        for n in range(_BOOM_ASYNC):
            _ = group.start_soon(one_boom, "/boom/async", f"boom-async-{n}")
        for n in range(_BOOM_SYNC):
            _ = group.start_soon(one_boom, "/boom/sync", f"boom-sync-{n}")

    return quiet_async, quiet_sync, boom_ids


def _forwarded_by_owner(
    collect: CollectingHandler, boom_ids: list[str]
) -> dict[str, tuple[LogRecord, ...]]:
    """Map each failed request to its one batch, refusing anything mixed or extra."""
    owners: dict[str, tuple[LogRecord, ...]] = {}
    for batch in collect.batches:
        ids = {cast("str", record.extra["request_id"]) for record in batch}
        assert len(ids) == 1, f"a forwarded batch mixes request ids: {sorted(ids)}"
        owner = ids.pop()
        assert owner not in owners, f"two batches were forwarded for {owner}"
        owners[owner] = batch
    assert set(owners) == set(boom_ids)
    for record in collect.singles:
        assert cast("str", record.extra["request_id"]) in set(boom_ids)
    return owners


def _uid_of(batch: tuple[LogRecord, ...]) -> str:
    uids = {cast("str", record.extra["uid"]) for record in batch}
    assert len(uids) == 1, f"one request's batch carries several uids: {sorted(uids)}"
    return uids.pop()


async def test_thirty_concurrent_requests_keep_their_own_logs_uid_and_trace() -> None:
    app = _application(_kernel("direct"))

    async with serving(app) as client:
        quiet_async, quiet_sync, boom_ids = await _drive(client)

    # Distinct X-Request-Id per request: minted for the quiet ones, kept
    # from the header for the failing ones.
    quiet_payloads = quiet_async + quiet_sync
    quiet_ids = [cast("str", payload["request_id"]) for payload in quiet_payloads]
    assert all(HEX_32.match(request_id) for request_id in quiet_ids)
    assert len(set(quiet_ids) | set(boom_ids)) == 30

    # Every forwarded batch belongs to exactly one failed request; the
    # quiet ones forwarded nothing below the passthru floor.
    collect = services.COLLECTED[-1]
    owners = _forwarded_by_owner(collect, boom_ids)
    assert set(quiet_ids).isdisjoint(owners)
    for batch in owners.values():
        criticals = [record for record in batch if record.level is Level.CRITICAL]
        assert len(criticals) == 1
        assert any(
            record.level is Level.DEBUG and record.message.startswith("about to fail")
            for record in batch
        ), "the debug record logged before the failure travels in its request's batch"

    # One uid per request, constant within it: the batch records — the sync
    # endpoint's worker-thread debug included — share theirs, the quiet
    # endpoints read the same one twice, and no two requests share.
    boom_uids = {owner: _uid_of(batch) for owner, batch in owners.items()}
    quiet_uids: list[str] = []
    for payload in quiet_payloads:
        first, second = cast("list[str]", payload["uids"])
        assert first == second
        quiet_uids.append(first)
    assert len(set(quiet_uids) | set(boom_uids.values())) == 30

    # A request's trace lists only its own events: its one probe, and every
    # listener of its own request event called exactly once.
    for payload in quiet_async:
        request_id = cast("str", payload["request_id"])
        assert cast("list[str]", payload["orphaned"]) == [f"probe.{request_id}"]
        assert cast("list[str]", payload["events"]) == [KernelEvents.REQUEST]
        assert set(cast("list[int]", payload["calls"])) == {1}


async def test_thirty_concurrent_requests_through_a_queue_keep_batches_apart() -> None:
    app = _application(_kernel("queued"))

    async with serving(app) as client:
        quiet_async, quiet_sync, boom_ids = await _drive(client)
    # Leaving the application life closed the factory, which closed the
    # queue: the worker has drained everything — no sleeps needed.

    quiet_ids = [cast("str", payload["request_id"]) for payload in quiet_async + quiet_sync]
    collect = services.COLLECTED[-1]
    owners = _forwarded_by_owner(collect, boom_ids)
    assert set(quiet_ids).isdisjoint(owners)
    for batch in owners.values():
        assert [record.level for record in batch].count(Level.CRITICAL) == 1
    assert len({_uid_of(batch) for batch in owners.values()}) == len(boom_ids)


async def test_a_console_style_boot_outside_http_logs_on_the_instance() -> None:
    async with await _kernel("direct").boot() as booted:
        logger = await booted.container.get(LoggerInterface)
        logger.debug("console work step", {"step": 1})
        logger.warning("console work went sideways", {"step": 2})

    # No unit of work was ever opened: the two records buffered on the
    # handler's instance state and left together when the warning released
    # it, both stamped with the one instance uid and no request id.
    collect = services.COLLECTED[-1]
    assert len(collect.batches) == 1
    batch = collect.batches[0]
    assert [record.level for record in batch] == [Level.DEBUG, Level.WARNING]
    assert len({cast("str", record.extra["uid"]) for record in batch}) == 1
    assert all("request_id" not in record.extra for record in batch)
    assert collect.singles == []
