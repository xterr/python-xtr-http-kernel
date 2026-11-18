from __future__ import annotations

import anyio
import anyio.lowlevel
import anyio.to_thread
import pytest
from xtr_dependency_injection.integration import detached_context

from xtr_http_kernel.data_collector import RequestTrace


def test_outside_a_request_nothing_is_recorded() -> None:
    trace: RequestTrace[str] = RequestTrace("outside")

    trace.record("lost")

    assert not trace.is_recording()
    assert trace.entries() == ()


def test_a_request_keeps_its_entries_in_order() -> None:
    trace: RequestTrace[str] = RequestTrace("ordered")
    trace.begin()

    trace.record("first")
    trace.record("second")

    assert trace.is_recording()
    assert trace.entries() == ("first", "second")


def test_beginning_again_starts_from_nothing() -> None:
    trace: RequestTrace[str] = RequestTrace("again")
    trace.begin()
    trace.record("old")

    trace.begin()

    assert trace.entries() == ()


def test_a_new_connection_starts_outside_the_request_it_was_copied_from() -> None:
    trace: RequestTrace[str] = RequestTrace("detached")
    trace.begin()
    trace.record("mid-request")

    assert not detached_context().run(trace.is_recording)
    assert trace.entries() == ("mid-request",)


@pytest.mark.anyio
async def test_concurrent_requests_each_keep_their_own() -> None:
    trace: RequestTrace[str] = RequestTrace("concurrent")
    seen: dict[str, tuple[str, ...]] = {}

    async def request(name: str) -> None:
        trace.begin()
        trace.record(name)
        await anyio.lowlevel.checkpoint()
        seen[name] = trace.entries()

    async with anyio.create_task_group() as group:
        _ = group.start_soon(request, "first")
        _ = group.start_soon(request, "second")

    assert seen == {"first": ("first",), "second": ("second",)}


@pytest.mark.anyio
async def test_a_worker_thread_records_into_the_request() -> None:
    trace: RequestTrace[str] = RequestTrace("threaded")
    trace.begin()

    await anyio.to_thread.run_sync(trace.record, "from a thread")

    assert trace.entries() == ("from a thread",)
