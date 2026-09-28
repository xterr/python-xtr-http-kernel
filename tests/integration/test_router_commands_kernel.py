"""The router commands as a booted kernel hands them over, configuration included."""

from __future__ import annotations

import io as streams
import sys
from typing import cast

import pytest
from xtr_console import ConsoleStyle, ExitCode
from xtr_dependency_injection import Kernel

from xtr_http_kernel.bundle import HttpKernelBundle
from xtr_http_kernel.command import DebugRouterCommand, RouterMatchCommand

pytestmark = pytest.mark.anyio


def _kernel() -> Kernel:
    return Kernel(
        "tests.fixtures.router_app",
        env="test",
        bundles={HttpKernelBundle: {"all": True}},
        resources=("tests.fixtures.router_app.configured_app",),
    )


def _capture() -> tuple[ConsoleStyle, streams.StringIO]:
    buffer = streams.StringIO()
    return ConsoleStyle(buffer, buffer, width=200, decorated=False), buffer


async def test_the_container_builds_the_listing_command_with_the_configured_application() -> None:
    style, buffer = _capture()

    async with await _kernel().boot() as booted:
        command = await booted.container.get(DebugRouterCommand)

        assert await command(style) == ExitCode.SUCCESS

    assert "/books/{isbn}" in buffer.getvalue()


async def test_the_container_builds_the_matching_command_with_the_configured_application() -> None:
    style, buffer = _capture()

    async with await _kernel().boot() as booted:
        command = await booted.container.get(RouterMatchCommand)

        assert await command(style, "/books/978") == ExitCode.SUCCESS

    assert "978" in buffer.getvalue()


async def test_without_a_console_the_commands_stay_out_of_the_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A ``None`` module entry makes the import fail, so the optional peer is
    # skipped exactly as if the console extra were not installed.
    modules = cast("dict[str, object]", sys.modules)
    monkeypatch.setitem(modules, "xtr_console.bundle", None)

    async with await _kernel().boot() as booted:
        assert not booted.container.has(DebugRouterCommand)
        assert not booted.container.has(RouterMatchCommand)
