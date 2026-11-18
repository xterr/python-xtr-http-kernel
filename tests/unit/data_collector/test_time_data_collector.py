from __future__ import annotations

from typing import cast

import pytest
from xtr_clock import MockClock
from xtr_stopwatch import Stopwatch

from tests.support.profiling import profiled
from xtr_http_kernel.data_collector.time_data_collector import TimeDataCollector


def test_the_duration_until_the_response_started_is_kept() -> None:
    clock = MockClock("2026-01-01 00:00:00")
    start = clock.now().timestamp()
    clock.sleep(0.25)

    data = TimeDataCollector(Stopwatch(), clock).collect(profiled(state={"_profiler.start": start}))

    assert data["start_time"] == start
    assert data["duration_ms"] == pytest.approx(250.0)


def test_without_an_arrival_there_is_no_duration() -> None:
    data = TimeDataCollector(Stopwatch()).collect(profiled())

    assert data == {"start_time": None, "duration_ms": None, "events": {}}


def test_once_sent_the_sections_events_are_kept() -> None:
    clock = MockClock("2026-01-01 00:00:00")
    stopwatch = Stopwatch(clock)
    stopwatch.open_section()
    _ = stopwatch.start("listener", "event_listener")
    clock.sleep(0.002)
    _ = stopwatch.stop("listener")
    stopwatch.stop_section("abc123")
    collector = TimeDataCollector(stopwatch, clock)
    request = profiled(state={"_profiler.token": "abc123"})

    data = collector.late_collect({"duration_ms": 1.0}, request)

    assert data["duration_ms"] == pytest.approx(2.0)
    assert set(cast("dict[str, object]", data["events"])) == {"__section__", "listener"}
    assert collector.name == "time"


def test_once_sent_a_request_without_a_token_keeps_what_it_had() -> None:
    data = TimeDataCollector(Stopwatch()).late_collect({"duration_ms": 1.0}, profiled())

    assert data == {"duration_ms": 1.0}


def test_once_sent_a_token_with_no_section_keeps_the_earlier_duration() -> None:
    data = TimeDataCollector(Stopwatch()).late_collect(
        {"duration_ms": 1.0}, profiled(state={"_profiler.token": "nope"})
    )

    assert data == {"duration_ms": 1.0, "origin": None, "events": {}}
