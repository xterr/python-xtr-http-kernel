from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from xtr_logging import DebugHandler, LogRecord, begin_unit, end_unit
from xtr_logging_contracts import Level

from tests.support.profiling import profiled
from xtr_http_kernel.data_collector.logger_data_collector import LoggerDataCollector


def _record(level: Level, message: str) -> LogRecord:
    return LogRecord(datetime(2026, 1, 1, tzinfo=UTC), "app", level, message, {"isbn": "42"})


def test_the_units_records_and_their_counts_are_kept() -> None:
    handler = DebugHandler()
    collector = LoggerDataCollector(handler)
    begin_unit()
    try:
        collector.begin_request()
        for level, message in ((Level.INFO, "a"), (Level.WARNING, "b"), (Level.ERROR, "c")):
            _ = handler.handle(_record(level, message))

        data = collector.late_collect(collector.collect(profiled()), profiled())
    finally:
        end_unit()

    assert data["error_count"] == 1
    assert data["warning_count"] == 1
    assert data["records"] == [
        {
            "time": "2026-01-01T00:00:00+00:00",
            "channel": "app",
            "level": level.name,
            "priority": int(level),
            "message": message,
            "context": {"isbn": {"kind": "str", "type": "str", "value": "42", "truncated": 0}},
        }
        for level, message in ((Level.INFO, "a"), (Level.WARNING, "b"), (Level.ERROR, "c"))
    ]
    assert collector.name == "logger"


def test_a_context_entry_named_like_a_credential_is_masked() -> None:
    handler = DebugHandler()
    collector = LoggerDataCollector(handler)
    record = LogRecord(
        datetime(2026, 1, 1, tzinfo=UTC),
        "app",
        Level.INFO,
        "signed in",
        {"user": "ana", "password": "hunter2", "api_token": "abc"},
    )
    begin_unit()
    try:
        collector.begin_request()
        _ = handler.handle(record)
        data = collector.late_collect({}, profiled())
    finally:
        end_unit()

    (kept,) = cast("list[dict[str, object]]", data["records"])
    assert kept["context"] == {
        "user": {"kind": "str", "type": "str", "value": "ana", "truncated": 0},
        "password": {"kind": "str", "type": "str", "value": "******", "truncated": 0},
        "api_token": {"kind": "str", "type": "str", "value": "******", "truncated": 0},
    }


def test_a_request_not_begun_keeps_no_record() -> None:
    handler = DebugHandler()
    collector = LoggerDataCollector(handler)
    begin_unit()
    try:
        _ = handler.handle(_record(Level.ERROR, "unprofiled"))

        data = collector.collect(profiled())
    finally:
        end_unit()

    assert data["records"] == []
    assert data["error_count"] == 0


def test_once_the_log_unit_closed_the_records_collected_with_the_response_stand() -> None:
    handler = DebugHandler()
    collector = LoggerDataCollector(handler)
    begin_unit()
    try:
        collector.begin_request()
        _ = handler.handle(_record(Level.ERROR, "kept"))
        data = collector.collect(profiled())
    finally:
        end_unit()

    assert collector.late_collect(data, profiled()) is data
    assert data["error_count"] == 1
