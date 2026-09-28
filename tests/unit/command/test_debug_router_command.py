"""Unit tests for :class:`xtr_http_kernel.command.DebugRouterCommand`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import ExitCode

from tests.unit.command.conftest import APPLICATION

if TYPE_CHECKING:
    from xtr_console import ApplicationTester

pytestmark = pytest.mark.anyio


async def test_every_route_of_the_application_is_listed(tester: ApplicationTester) -> None:
    code = await tester.execute(["debug:router", "--app", APPLICATION])

    assert code == ExitCode.SUCCESS
    for expected in ("Methods", "Path", "Name", "Endpoint"):
        assert expected in tester.display
    assert "/books/{isbn}" in tester.display
    assert "tests.fixtures.router_app.app:book" in tester.display


async def test_an_included_router_is_listed_only_under_its_prefix(
    tester: ApplicationTester,
) -> None:
    _ = await tester.execute(["debug:router", "--app", APPLICATION])

    assert "/books/{isbn}" in tester.display
    assert "/{isbn}" not in tester.display.replace("/books/{isbn}", "")


async def test_a_connection_route_and_a_mount_are_listed_with_their_kind(
    tester: ApplicationTester,
) -> None:
    _ = await tester.execute(["debug:router", "--app", APPLICATION])

    assert "WEBSOCKET" in tester.display
    assert "MOUNT" in tester.display


async def test_every_route_is_counted(tester: ApplicationTester) -> None:
    _ = await tester.execute(["debug:router", "--app", APPLICATION])

    assert "Routes (8)" in tester.display


async def test_without_an_application_nothing_is_listed(tester: ApplicationTester) -> None:
    code = await tester.execute(["debug:router"])

    assert code == ExitCode.INVALID
    assert "Endpoint" not in tester.display
