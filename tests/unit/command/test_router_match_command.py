"""Unit tests for :class:`xtr_http_kernel.command.RouterMatchCommand`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import ExitCode

from tests.support.route_listing import lists_included_routers
from tests.unit.command.conftest import APPLICATION
from xtr_http_kernel.bundle import HttpKernelConfig
from xtr_http_kernel.command import RouterMatchCommand

if TYPE_CHECKING:
    import io as streams

    from xtr_console import ApplicationTester, ConsoleStyle

pytestmark = pytest.mark.anyio


@lists_included_routers
async def test_a_matching_path_names_the_route_and_its_parameters(
    tester: ApplicationTester,
) -> None:
    code = await tester.execute(["router:match", "/books/123", "--app", APPLICATION])

    assert code == ExitCode.SUCCESS
    assert "book" in tester.display
    assert "/books/{isbn}" in tester.display
    assert "tests.fixtures.router_app.app:book" in tester.display
    assert "isbn" in tester.display
    assert "123" in tester.display


async def test_a_route_without_parameters_matches_too(tester: ApplicationTester) -> None:
    code = await tester.execute(
        ["router:match", "/orders", "--method", "POST", "--app", APPLICATION]
    )

    assert code == ExitCode.SUCCESS
    assert "place_order" in tester.display
    assert "Parameter" not in tester.display


async def test_a_method_in_lower_case_is_read_as_the_method_it_names(
    tester: ApplicationTester,
) -> None:
    code = await tester.execute(
        ["router:match", "/orders", "--method", "post", "--app", APPLICATION]
    )

    assert code == ExitCode.SUCCESS


async def test_a_path_matched_by_a_route_that_refuses_the_method_reports_the_near_miss(
    tester: ApplicationTester,
) -> None:
    code = await tester.execute(["router:match", "/orders", "--app", APPLICATION])

    assert code == ExitCode.FAILURE
    assert "place_order" in tester.display
    assert "GET" in tester.display


async def test_a_path_no_route_answers_says_so(tester: ApplicationTester) -> None:
    code = await tester.execute(["router:match", "/nope", "--app", APPLICATION])

    assert code == ExitCode.FAILURE
    assert "no route matches" in tester.display


async def test_a_mounted_application_is_matched_as_the_mount(tester: ApplicationTester) -> None:
    code = await tester.execute(["router:match", "/inner/ping", "--app", APPLICATION])

    assert code == ExitCode.SUCCESS
    assert "inner" in tester.display


async def test_the_configured_application_needs_no_option(
    captured: tuple[ConsoleStyle, streams.StringIO],
) -> None:
    style, buffer = captured
    command = RouterMatchCommand(HttpKernelConfig(app=APPLICATION))

    assert await command(style, "/orders", method="POST") == ExitCode.SUCCESS
    assert "place_order" in buffer.getvalue()


async def test_without_an_application_it_matches_nothing(tester: ApplicationTester) -> None:
    code = await tester.execute(["router:match", "/books/123"])

    assert code == ExitCode.INVALID
    assert "--app" in tester.display
