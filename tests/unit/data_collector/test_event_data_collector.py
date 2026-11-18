from __future__ import annotations

from typing import cast

import pytest
from xtr_event_dispatcher import Event, EventDispatcher
from xtr_event_dispatcher.debug import TraceableEventDispatcher

from tests.support.profiling import profiled
from xtr_http_kernel.data_collector.event_data_collector import EventDataCollector

pytestmark = pytest.mark.anyio


def _heard(event: object) -> None:
    del event


def _unheard(event: object) -> None:
    del event


async def test_a_traced_dispatchers_listeners_and_orphans_are_kept() -> None:
    inner = EventDispatcher()
    inner.add_listener("order.placed", _heard, 5)
    inner.add_listener("order.shipped", _unheard)
    traced = TraceableEventDispatcher(inner)
    _ = await traced.dispatch(Event(), "order.placed")
    _ = await traced.dispatch(Event(), "nobody.listens")
    collector = EventDataCollector(traced)

    data = collector.late_collect(collector.collect(profiled()), profiled())

    called = cast("list[dict[str, object]]", data["called"])
    not_called = cast("list[dict[str, object]]", data["not_called"])
    assert data["traced"] is True
    assert [
        (info["event"], info["listener"], info["priority"], info["calls"]) for info in called
    ] == [("order.placed", f"{__name__}._heard", 5, 1)]
    assert [info["listener"] for info in not_called] == [f"{__name__}._unheard"]
    assert data["orphaned"] == ["nobody.listens"]
    assert collector.name == "events"


def test_an_untraced_dispatcher_has_nothing_to_read() -> None:
    collector = EventDataCollector(EventDispatcher())

    data = collector.late_collect(collector.collect(profiled()), profiled())

    assert data == {"traced": False}
