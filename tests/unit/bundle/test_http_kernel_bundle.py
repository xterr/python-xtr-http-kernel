"""Unit tests for :class:`xtr_http_kernel.bundle.HttpKernelBundle`."""

from __future__ import annotations

import pytest
from xtr_dependency_injection.testing import assert_zero_config
from xtr_event_dispatcher.bundle import EventDispatcherBundle

from xtr_http_kernel.bundle import HttpKernelBundle, HttpKernelConfig

pytestmark = pytest.mark.anyio


async def test_zero_config_boots_and_shuts_down() -> None:
    await assert_zero_config(HttpKernelBundle)


def test_the_bundle_is_named_and_carries_its_config() -> None:
    metadata = HttpKernelBundle.metadata()

    assert metadata.name == "http_kernel"
    assert metadata.config is HttpKernelConfig


def test_the_config_is_buildable_with_no_arguments() -> None:
    assert HttpKernelConfig() == HttpKernelConfig()


def test_the_bundle_requires_the_event_dispatcher_and_its_optional_peers() -> None:
    targets = {declaration.target for declaration in HttpKernelBundle.metadata().required}

    assert EventDispatcherBundle in targets
    assert "xtr_logging.bundle:LoggingBundle" in targets
    assert "xtr_console.bundle:ConsoleBundle" in targets
