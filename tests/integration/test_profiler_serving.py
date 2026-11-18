"""A served application with the profiler on: every request leaves a profile."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import anyio
import pytest
from fastapi import FastAPI
from xtr_dependency_injection import Injected, Kernel
from xtr_logging_contracts import LoggerInterface

from tests.support.serving import serving
from xtr_http_kernel import setup
from xtr_http_kernel.bundle import HttpKernelBundle
from xtr_http_kernel.profiler import FileProfilerStorage, Profile, Profiler

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

pytestmark = pytest.mark.anyio

_APP = "tests.fixtures.profiled_app"
_OVERRIDES = "tests.fixtures.profiled_overrides"


@pytest.fixture
def folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PROFILER_TEST_FOLDER", str(tmp_path))
    return tmp_path


def _application(settings: str, *, debug: bool = True) -> FastAPI:
    kernel = Kernel(
        _APP,
        env="test",
        debug=debug,
        bundles={HttpKernelBundle: {"all": True}},
        resources=(_APP, f"{_OVERRIDES}.{settings}"),
    )
    app = FastAPI()

    @app.get("/books/{isbn}", name="show_book")
    async def show_book(isbn: str, logger: Injected[LoggerInterface]) -> dict[str, str]:
        logger.warning("book {isbn} read", {"isbn": isbn})
        await anyio.lowlevel.checkpoint()
        return {"isbn": isbn}

    @app.get("/boom")
    async def boom() -> dict[str, str]:
        message = "boom"
        raise RuntimeError(message)

    @app.get("/_profiler/latest")
    async def profiler_page() -> dict[str, str]:
        return {"page": "profiler"}

    setup(app, kernel)
    return app


def _stored(folder: Path, token: str) -> Profile:
    profile = FileProfilerStorage(folder).read(token)
    assert profile is not None
    return profile


def _app_records(profile: Profile) -> list[Mapping[str, object]]:
    """The records the endpoint logged, without the traced dispatcher's own."""
    records = cast("list[Mapping[str, object]]", profile.get_collector("logger")["records"])
    return [record for record in records if record["channel"] == "app"]


async def test_a_profiled_response_names_its_profile(folder: Path) -> None:
    async with serving(_application("enabled")) as client:
        response = await client.get("/books/42?q=dune", headers={"Authorization": "Bearer x"})

    token = response.headers["x-debug-token"]
    profile = _stored(folder, token)
    assert (profile.method, profile.status_code) == ("GET", 200)
    assert profile.url == "http://served.test/books/42?q=dune"
    # A peer bundle active here (the cache, through the rate limiter) adds its own panel;
    # only the kernel's panels and their order are under test.
    core = [
        "request",
        "time",
        "memory",
        "ajax",
        "exception",
        "logger",
        "events",
        "router",
        "config",
    ]
    assert [name for name in profile.collectors if name in core] == core


async def test_the_request_panel_keeps_the_head_and_masks_credentials(folder: Path) -> None:
    async with serving(_application("enabled")) as client:
        response = await client.get("/books/42?q=dune", headers={"Authorization": "Bearer x"})

    request = _stored(folder, response.headers["x-debug-token"]).get_collector("request")
    headers = cast("Mapping[str, str]", request["request_headers"])
    assert headers["authorization"] == "******"
    assert request["query"] == {"q": "dune"}
    assert request["status_code"] == 200
    assert "******" in cast("str", request["curl_command"])
    assert "_profiler.start" not in cast("Mapping[str, object]", request["state"])


async def test_the_router_panel_names_the_route_that_answered(folder: Path) -> None:
    async with serving(_application("enabled")) as client:
        response = await client.get("/books/42")

    router = _stored(folder, response.headers["x-debug-token"]).get_collector("router")
    assert router["matched"] is True
    assert router["name"] == "show_book"
    assert router["path"] == "/books/{isbn}"
    assert router["path_params"] == {"isbn": "42"}


async def test_the_time_panel_holds_the_listeners_and_the_application_on_one_timeline(
    folder: Path,
) -> None:
    async with serving(_application("enabled")) as client:
        response = await client.get("/books/42")

    time = _stored(folder, response.headers["x-debug-token"]).get_collector("time")
    events = cast("Mapping[str, Mapping[str, object]]", time["events"])
    assert "__section__" in events
    assert events["controller"]["category"] == "section"
    assert any(event["category"] == "event_listener" for event in events.values())
    assert cast("float", time["duration_ms"]) >= 0.0


async def test_the_log_panel_holds_what_the_request_logged(folder: Path) -> None:
    async with serving(_application("enabled")) as client:
        response = await client.get("/books/42")

    profile = _stored(folder, response.headers["x-debug-token"])
    assert [record["message"] for record in _app_records(profile)] == ["book {isbn} read"]
    assert profile.get_collector("logger")["warning_count"] == 1


async def test_the_events_panel_lists_the_listeners_called(folder: Path) -> None:
    async with serving(_application("enabled")) as client:
        response = await client.get("/books/42")

    events = _stored(folder, response.headers["x-debug-token"]).get_collector("events")
    called = cast("list[Mapping[str, object]]", events["called"])
    assert events["traced"] is True
    assert any("ProfilerListener" in cast("str", info["listener"]) for info in called)


async def test_a_failure_nobody_answered_is_profiled_as_a_500(folder: Path) -> None:
    async with serving(_application("enabled")) as client:
        response = await client.get("/boom")

    assert response.status_code == 500
    (entry,) = FileProfilerStorage(folder).find(None, "/boom", 10, None)
    profile = _stored(folder, entry.token)
    exception = profile.get_collector("exception")
    chain = cast("list[Mapping[str, object]]", exception["chain"])
    assert profile.status_code == 500
    assert profile.has_errors
    assert chain[0]["class"] == "RuntimeError"
    assert chain[0]["message"] == "boom"


async def test_the_profilers_own_pages_are_not_profiled(folder: Path) -> None:
    async with serving(_application("enabled")) as client:
        response = await client.get("/_profiler/latest")

    assert "x-debug-token" not in response.headers
    assert FileProfilerStorage(folder).find(None, None, 10, None) == []


async def test_with_collecting_off_only_a_request_asking_is_profiled(folder: Path) -> None:
    async with serving(_application("on_demand")) as client:
        plain = await client.get("/books/1")
        asked = await client.get("/books/2?profile=1")

    assert "x-debug-token" not in plain.headers
    assert _stored(folder, asked.headers["x-debug-token"]).url.endswith("/books/2?profile=1")


async def test_only_exceptions_keeps_the_failures_alone(folder: Path) -> None:
    async with serving(_application("only_exceptions")) as client:
        fine = await client.get("/books/1")
        _ = await client.get("/boom")

    assert "x-debug-token" not in fine.headers
    assert [entry.url for entry in FileProfilerStorage(folder).find(None, None, 10, None)] == [
        "http://served.test/boom"
    ]


async def test_concurrent_requests_each_get_a_profile_of_their_own(folder: Path) -> None:
    tokens: dict[str, str] = {}

    async with serving(_application("enabled")) as client:

        async def fetch(isbn: str) -> None:
            response = await client.get(f"/books/{isbn}")
            tokens[isbn] = response.headers["x-debug-token"]

        async with anyio.create_task_group() as group:
            for isbn in ("1", "2", "3"):
                _ = group.start_soon(fetch, isbn)

    for isbn, token in tokens.items():
        profile = _stored(folder, token)
        assert profile.get_collector("router")["path_params"] == {"isbn": isbn}
        assert [record["context"] for record in _app_records(profile)] == [
            {"isbn": {"kind": "str", "type": "str", "value": isbn, "truncated": 0}}
        ]


async def test_outside_debug_the_profile_has_no_log_panel(folder: Path) -> None:
    async with serving(_application("enabled", debug=False)) as client:
        response = await client.get("/books/42")

    profile = _stored(folder, response.headers["x-debug-token"])
    assert not profile.has_collector("logger")
    assert profile.get_collector("events") == {"traced": False}


async def test_with_the_profiler_off_nothing_of_it_is_registered() -> None:
    kernel = Kernel(_APP, env="test", debug=True, bundles={HttpKernelBundle: {"all": True}})

    async with await kernel.boot() as booted:
        assert not booted.container.has(Profiler)
