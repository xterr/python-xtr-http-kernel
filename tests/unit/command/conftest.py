"""The router commands under a console, built with a configuration as a container builds them."""

from __future__ import annotations

import io as streams
from typing import TYPE_CHECKING, cast, final

import pytest
from typing_extensions import override
from xtr_console import Application, ApplicationTester, CommandInvokerInterface, ConsoleStyle

from xtr_http_kernel.bundle import HttpKernelConfig

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xtr_console.command import CommandArguments, CommandDescriptor, CommandSignature

    from xtr_http_kernel.command.router_command import RouterCommand

APPLICATION = "tests.fixtures.router_app.app:app"
"""The import string the fixture application answers to."""


@final
class _ConfiguringInvoker(CommandInvokerInterface):
    """Builds a router command with a configuration, as a container would."""

    def __init__(self, config: HttpKernelConfig) -> None:
        self._config = config

    @override
    async def invoke(
        self,
        command: CommandDescriptor,
        signature: CommandSignature,
        arguments: CommandArguments,
    ) -> object:
        del signature
        command_type = cast("type[RouterCommand]", command.target)
        # The arguments come parsed off the command line, typed only as objects.
        call = cast("Callable[..., Awaitable[object]]", command_type(self._config))
        return await call(*arguments.args, **arguments.kwargs)


@pytest.fixture
def tester() -> ApplicationTester:
    application = Application("test", catch_exceptions=False)
    application.use_invoker(_ConfiguringInvoker(HttpKernelConfig()))
    # Wide enough that no table column is truncated before a test reads it.
    return ApplicationTester(application, width=200)


@pytest.fixture
def captured() -> tuple[ConsoleStyle, streams.StringIO]:
    """A style writing into one buffer, for a command driven without the tester."""
    buffer = streams.StringIO()
    return ConsoleStyle(buffer, buffer, width=200, decorated=False), buffer
