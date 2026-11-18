from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from starlette.datastructures import MutableHeaders
from xtr_http_message import ServerRequest
from xtr_stopwatch import Stopwatch

from xtr_http_kernel.event import ExceptionEvent, RequestEvent, ResponseEvent, TerminateEvent
from xtr_http_kernel.event_listener.profiler_listener import ProfilerListener
from xtr_http_kernel.profiler import FileProfilerStorage, Profiler

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_http_kernel.data_collector import ProfiledRequest

pytestmark = pytest.mark.anyio


class _Status:
    @property
    def name(self) -> str:
        return "status"

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        return {"status": profiled.status_code}


def _request(uri: str = "http://shop.test/books") -> ServerRequest:
    return ServerRequest("GET", uri)


@pytest.fixture
def storage(tmp_path: Path) -> FileProfilerStorage:
    return FileProfilerStorage(tmp_path)


def _listener(  # noqa: PLR0913 — one keyword per setting a test varies
    storage: FileProfilerStorage,
    *,
    collect: bool = True,
    collect_parameter: str | None = None,
    only_exceptions: bool = False,
    excluded_paths: tuple[str, ...] = ("^/_profiler",),
    excluded_status_codes: tuple[int, ...] = (),
) -> tuple[ProfilerListener, Profiler]:
    profiler = Profiler(storage, [_Status()], enabled=collect)
    listener = ProfilerListener(
        profiler,
        Stopwatch(),
        collect_parameter=collect_parameter,
        only_exceptions=only_exceptions,
        excluded_paths=excluded_paths,
        excluded_status_codes=excluded_status_codes,
    )
    return listener, profiler


async def _serve(
    listener: ProfilerListener,
    request: ServerRequest,
    state: dict[str, object] | None = None,
    *,
    status: int = 200,
    exception: BaseException | None = None,
) -> MutableHeaders | None:
    """Run the listener through one request; return the response head, if one started."""
    bag: dict[str, object] = state if state is not None else {}
    listener.on_request(RequestEvent(request, bag))
    listener.on_request_late(RequestEvent(request, bag))
    if exception is not None:
        listener.on_exception(ExceptionEvent(request, bag, exception))
    headers: MutableHeaders | None = None
    if exception is None:
        headers = MutableHeaders()
        listener.on_response(ResponseEvent(request, bag, status, headers))
    await listener.on_terminate(TerminateEvent(request, bag, status))
    return headers


async def test_a_profiled_response_carries_its_token_and_the_profile_is_stored(
    storage: FileProfilerStorage,
) -> None:
    listener, _ = _listener(storage)

    headers = await _serve(listener, _request())

    assert headers is not None
    profile = storage.read(headers["x-debug-token"])
    assert profile is not None
    assert profile.get_collector("status") == {"status": 200}


async def test_an_excluded_path_is_not_profiled(storage: FileProfilerStorage) -> None:
    listener, _ = _listener(storage)

    headers = await _serve(listener, _request("http://shop.test/_profiler/abc"))

    assert headers is not None
    assert "x-debug-token" not in headers


@pytest.mark.parametrize(
    ("collect", "uri", "profiled"),
    [
        (False, "http://shop.test/?profile=1", True),
        (False, "http://shop.test/?profile=yes", True),
        (False, "http://shop.test/?profile=maybe", False),
        (False, "http://shop.test/", False),
        (True, "http://shop.test/?profile=0", False),
        (True, "http://shop.test/?profile=", False),
    ],
)
async def test_the_collect_parameter_turns_profiling_on_or_off(
    storage: FileProfilerStorage, collect: bool, uri: str, profiled: bool
) -> None:
    listener, _ = _listener(storage, collect=collect, collect_parameter="profile")

    headers = await _serve(listener, _request(uri))

    assert headers is not None
    assert ("x-debug-token" in headers) is profiled


async def test_the_collect_parameter_may_be_a_state_entry(storage: FileProfilerStorage) -> None:
    listener, _ = _listener(storage, collect=False, collect_parameter="profile")

    headers = await _serve(listener, _request(), {"profile": True})

    assert headers is not None
    assert "x-debug-token" in headers


async def test_a_state_entry_that_is_no_text_asks_nothing(storage: FileProfilerStorage) -> None:
    listener, _ = _listener(storage, collect=False, collect_parameter="profile")

    headers = await _serve(listener, _request(), {"profile": 1})

    assert headers is not None
    assert "x-debug-token" not in headers


async def test_only_exceptions_skips_a_request_that_did_not_raise(
    storage: FileProfilerStorage,
) -> None:
    listener, _ = _listener(storage, only_exceptions=True)

    headers = await _serve(listener, _request())

    assert headers is not None
    assert "x-debug-token" not in headers


async def test_an_excluded_status_is_not_kept(storage: FileProfilerStorage) -> None:
    listener, _ = _listener(storage, excluded_status_codes=(404,))

    headers = await _serve(listener, _request(), status=404)

    assert headers is not None
    assert "x-debug-token" not in headers


async def test_a_failure_whose_response_never_started_is_profiled_as_a_500(
    storage: FileProfilerStorage,
) -> None:
    listener, _ = _listener(storage)

    _ = await _serve(listener, _request(), status=500, exception=RuntimeError("boom"))

    (entry,) = storage.find(None, None, 10, None)
    assert entry.status_code == 500
    assert entry.has_errors


async def test_a_request_the_listener_never_saw_arrive_is_left_alone(
    storage: FileProfilerStorage,
) -> None:
    listener, _ = _listener(storage)

    await listener.on_terminate(TerminateEvent(_request(), {}, 200))

    assert storage.find(None, None, 10, None) == []
