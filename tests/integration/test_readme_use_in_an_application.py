"""The README's *Activate* / *Brings along* claims, checked against a build.

The *Use in an application* section promises that listing only
``HttpKernelBundle`` gives ``http_kernel`` itself as ``listed`` and ``active``,
the event dispatcher as ``required``, and — the logging and console packages
being installed here — those two as ``required`` too. The report the kernel
freezes at compile time says exactly that, so the claim cannot drift from the
code without this failing.
"""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel

from xtr_http_kernel.bundle import HttpKernelBundle

pytestmark = pytest.mark.anyio


def _report() -> str:
    # No resources: the bundle and its required peers are the whole build.
    kernel = Kernel(
        "xtr_http_kernel.bundle",
        env="test",
        bundles={HttpKernelBundle: {"all": True}},
        resources=(),
    )
    return kernel.build().report.render("bundles")


async def test_http_kernel_is_listed_and_active() -> None:
    lines = [line for line in _report().splitlines() if line.startswith("http_kernel")]

    assert len(lines) == 1
    assert "listed" in lines[0]
    assert "active" in lines[0]


async def test_the_event_dispatcher_is_pulled_in_as_a_required_peer() -> None:
    lines = [line for line in _report().splitlines() if line.startswith("event_dispatcher")]

    assert len(lines) == 1
    assert "required" in lines[0]
    assert "active" in lines[0]


async def test_logging_and_console_are_required_when_installed() -> None:
    report = _report()

    for name in ("logging", "console"):
        lines = [line for line in report.splitlines() if line.startswith(name)]
        assert len(lines) == 1, name
        assert "required" in lines[0], name
        assert "active" in lines[0], name
