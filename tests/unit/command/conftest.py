"""The router commands run without a container, told which application to read."""

from __future__ import annotations

import io as streams

import pytest
from xtr_console import Application, ApplicationTester, ConsoleStyle

APPLICATION = "tests.fixtures.router_app.app:app"
"""The import string the fixture application answers to."""


@pytest.fixture
def tester() -> ApplicationTester:
    # Wide enough that no table column is truncated before a test reads it.
    return ApplicationTester(Application("test", catch_exceptions=False), width=200)


@pytest.fixture
def captured() -> tuple[ConsoleStyle, streams.StringIO]:
    """A style writing into one buffer, for a command driven without the tester."""
    buffer = streams.StringIO()
    return ConsoleStyle(buffer, buffer, width=200, decorated=False), buffer
