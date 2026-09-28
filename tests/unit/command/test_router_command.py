"""Where a router command's application comes from, and what it says when none does.

:class:`~xtr_http_kernel.command.router_command.RouterCommand` is what both
commands inherit it from, so it is driven here through the thinnest of the
two rather than reached into.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import ExitCode

from tests.unit.command.conftest import APPLICATION
from xtr_http_kernel.bundle import HttpKernelConfig
from xtr_http_kernel.command import DebugRouterCommand

if TYPE_CHECKING:
    import io as streams

    from xtr_console import ConsoleStyle

pytestmark = pytest.mark.anyio

NOT_AN_APPLICATION = "tests.fixtures.router_app.app:books"
"""An attribute of the fixture module that is a router, not an application."""


async def test_the_option_names_the_application(
    captured: tuple[ConsoleStyle, streams.StringIO],
) -> None:
    style, buffer = captured

    assert await DebugRouterCommand()(style, app=APPLICATION) == ExitCode.SUCCESS
    assert "/orders" in buffer.getvalue()


async def test_the_configuration_names_the_application_when_no_option_does(
    captured: tuple[ConsoleStyle, streams.StringIO],
) -> None:
    style, buffer = captured
    command = DebugRouterCommand(HttpKernelConfig(app=APPLICATION))

    assert await command(style) == ExitCode.SUCCESS
    assert "/orders" in buffer.getvalue()


async def test_the_option_wins_over_the_configuration(
    captured: tuple[ConsoleStyle, streams.StringIO],
) -> None:
    style, buffer = captured
    command = DebugRouterCommand(HttpKernelConfig(app=NOT_AN_APPLICATION))

    assert await command(style, app=APPLICATION) == ExitCode.SUCCESS
    assert "does not name an application" not in buffer.getvalue()


async def test_without_an_application_anywhere_it_says_how_to_name_one(
    captured: tuple[ConsoleStyle, streams.StringIO],
) -> None:
    style, buffer = captured

    assert await DebugRouterCommand()(style) == ExitCode.INVALID
    assert "--app" in buffer.getvalue()


async def test_a_reference_without_an_attribute_is_refused(
    captured: tuple[ConsoleStyle, streams.StringIO],
) -> None:
    style, buffer = captured

    code = await DebugRouterCommand()(style, app="tests.fixtures.router_app.app")

    assert code == ExitCode.INVALID
    assert "package.module:app" in buffer.getvalue()


async def test_a_module_that_cannot_be_imported_is_reported(
    captured: tuple[ConsoleStyle, streams.StringIO],
) -> None:
    style, buffer = captured

    code = await DebugRouterCommand()(style, app="tests.fixtures.no_such_module:app")

    assert code == ExitCode.INVALID
    assert "cannot import" in buffer.getvalue()


async def test_an_attribute_that_is_not_an_application_is_reported(
    captured: tuple[ConsoleStyle, streams.StringIO],
) -> None:
    style, buffer = captured

    assert await DebugRouterCommand()(style, app=NOT_AN_APPLICATION) == ExitCode.INVALID
    assert "does not name an application" in buffer.getvalue()
