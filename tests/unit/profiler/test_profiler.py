from __future__ import annotations

from typing import TYPE_CHECKING, final

import anyio
import pytest
from xtr_clock import MockClock
from xtr_http_message import ServerRequest

from xtr_http_kernel.data_collector import ProfiledRequest
from xtr_http_kernel.profiler import FileProfilerStorage, Profile, Profiler

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio


@final
class _MethodCollector:
    @property
    def name(self) -> str:
        return "method"

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        return {"method": profiled.request.get_method()}


@final
class _LateCollector:
    @property
    def name(self) -> str:
        return "logger"

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        del profiled
        return {"error_count": 0}

    def late_collect(self, data: dict[str, object], profiled: ProfiledRequest) -> dict[str, object]:
        del profiled
        return {**data, "error_count": 2}


def _profiled(exception: BaseException | None = None) -> ProfiledRequest:
    request = ServerRequest(
        "POST", "http://shop.test/books?x=1", server_params={"client": ("10.1.2.3", 5000)}
    )
    return ProfiledRequest(request, 201, {"content-type": "text/html"}, {}, exception)


@pytest.fixture
def profiler(tmp_path: Path) -> Profiler:
    clock = MockClock("2026-01-01 00:00:00")
    storage = FileProfilerStorage(tmp_path, clock=clock)
    return Profiler(storage, [_MethodCollector(), _LateCollector()], clock)


async def test_a_profile_holds_the_request_head_and_every_collectors_data(
    profiler: Profiler,
) -> None:
    profile = profiler.collect(_profiled())

    assert profile is not None
    assert len(profile.token) == 6
    assert (profile.ip, profile.method, profile.url) == (
        "10.1.2.3",
        "POST",
        "http://shop.test/books?x=1",
    )
    assert profile.status_code == 201
    assert profile.time == 1_767_225_600
    assert profile.get_collector("method") == {"method": "POST"}
    assert not profile.has_errors


async def test_a_client_the_server_did_not_name_is_unknown(tmp_path: Path) -> None:
    profiler = Profiler(FileProfilerStorage(tmp_path))
    request = ServerRequest("GET", "http://shop.test/")

    profile = profiler.collect(ProfiledRequest(request, 200, {}, {}))

    assert profile is not None
    assert profile.ip == "Unknown"


async def test_an_exception_marks_the_profile_as_having_errors(profiler: Profiler) -> None:
    profile = profiler.collect(_profiled(RuntimeError("boom")))

    assert profile is not None
    assert profile.has_errors


async def test_saving_completes_the_late_collectors_and_reads_logged_errors(
    profiler: Profiler,
) -> None:
    profiled = _profiled()
    profile = profiler.collect(profiled)
    assert profile is not None

    assert await profiler.save_profile(profile, profiled)

    loaded = await profiler.load_profile(profile.token)
    assert loaded is not None
    assert loaded.get_collector("logger") == {"error_count": 2}
    assert loaded.has_errors


async def test_a_profile_is_found_from_the_response_headers(profiler: Profiler) -> None:
    profiled = _profiled()
    profile = profiler.collect(profiled)
    assert profile is not None
    _ = await profiler.save_profile(profile, profiled)

    loaded = await profiler.load_profile_from_response({"x-debug-token": profile.token})

    assert loaded is not None
    assert loaded.token == profile.token
    assert await profiler.load_profile_from_response({}) is None


async def test_find_and_purge_go_through_the_storage(profiler: Profiler) -> None:
    profiled = _profiled()
    profile = profiler.collect(profiled)
    assert profile is not None
    _ = await profiler.save_profile(profile, profiled)

    assert [entry.token for entry in await profiler.find(None, None, 10, "post")] == [profile.token]
    await profiler.purge()
    assert await profiler.find(None, None, 10, None) == []


async def test_a_disabled_request_is_not_profiled(profiler: Profiler) -> None:
    profiler.begin_request()
    profiler.disable()

    assert not profiler.is_enabled()
    assert profiler.collect(_profiled()) is None

    profiler.enable()
    assert profiler.collect(_profiled()) is not None


async def test_enabling_is_decided_per_request(profiler: Profiler) -> None:
    seen: dict[str, bool] = {}

    async def request(name: str, *, disable: bool) -> None:
        profiler.begin_request()
        if disable:
            profiler.disable()
        await anyio.lowlevel.checkpoint()
        seen[name] = profiler.is_enabled()

    async with anyio.create_task_group() as group:
        _ = group.start_soon(lambda: request("off", disable=True))
        _ = group.start_soon(lambda: request("on", disable=False))

    assert seen == {"off": False, "on": True}
    assert profiler.is_enabled()


async def test_setting_the_detached_variable_back_forgets_the_requests_decision(
    profiler: Profiler,
) -> None:
    profiler.begin_request()
    profiler.disable()
    variable, value = profiler.detached_variable

    _ = variable.set(value)

    assert profiler.is_enabled()


async def test_profiling_is_off_by_default_when_configured_off(tmp_path: Path) -> None:
    profiler = Profiler(FileProfilerStorage(tmp_path), enabled=False)

    assert not profiler.is_enabled()
    profiler.begin_request()
    assert not profiler.is_enabled()


async def test_the_collectors_are_known_by_name(profiler: Profiler) -> None:
    assert profiler.has("method")
    assert not profiler.has("router")
    assert profiler.get("router") is None
    assert [collector.name for collector in profiler.all()] == ["method", "logger"]
    assert repr(profiler) == "Profiler(collectors=['method', 'logger'])"


async def test_a_profile_without_a_logger_collector_has_no_logged_errors(tmp_path: Path) -> None:
    profiler = Profiler(FileProfilerStorage(tmp_path))
    profiled = _profiled()
    profile = Profile("abcdef")

    _ = await profiler.save_profile(profile, profiled)

    assert not profile.has_errors


@final
class _Tracing:
    def __init__(self) -> None:
        self.begun = 0

    @property
    def name(self) -> str:
        return "tracing"

    def begin_request(self) -> None:
        self.begun += 1

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        del profiled
        return {}


async def test_a_profiled_request_starts_every_tracing_collector(tmp_path: Path) -> None:
    tracing = _Tracing()
    profiler = Profiler(FileProfilerStorage(tmp_path), [_MethodCollector(), tracing])
    profiler.begin_request()

    profiler.begin_tracing()

    assert tracing.begun == 1


async def test_an_unprofiled_request_starts_no_tracing_collector(tmp_path: Path) -> None:
    tracing = _Tracing()
    profiler = Profiler(FileProfilerStorage(tmp_path), [tracing])
    profiler.begin_request()
    profiler.disable()

    profiler.begin_tracing()

    assert tracing.begun == 0
