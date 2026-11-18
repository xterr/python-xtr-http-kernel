"""Another bundle asks whether requests are profiled, before registering a collector."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final, override

import pytest
from xtr_dependency_injection import Bundle, Kernel, as_bundle
from xtr_dependency_injection.bundle.bundle import AnyBundle

from xtr_http_kernel.bundle import HttpKernelBundle, profiling_active

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator


@final
@as_bundle("asking")
class AskingBundle(Bundle):
    """Notes what profiling_active answered while it loaded."""

    answers: ClassVar[list[bool]] = []

    @override
    def load_extension(
        self, config: object, services: ServiceConfigurator, builder: ContainerBuilder
    ) -> None:
        del config, services
        AskingBundle.answers.append(profiling_active(builder))


@pytest.fixture(autouse=True)
def _clear(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    AskingBundle.answers.clear()
    monkeypatch.setenv("PROFILER_TEST_FOLDER", str(tmp_path))


def _build(*resources: str, with_kernel: bool = True) -> None:
    bundles: dict[type[AnyBundle], dict[str, bool]] = {AskingBundle: {"all": True}}
    if with_kernel:
        bundles[HttpKernelBundle] = {"all": True}
    _ = Kernel("xtr_http_kernel.bundle", env="test", bundles=bundles, resources=resources).build()


def test_with_the_profiler_on_profiling_is_active() -> None:
    _build("tests.fixtures.profiled_overrides.enabled")

    assert AskingBundle.answers == [True]


def test_with_the_profiler_off_it_is_not() -> None:
    _build()

    assert AskingBundle.answers == [False]


def test_without_the_http_kernel_it_is_not() -> None:
    _build(with_kernel=False)

    assert AskingBundle.answers == [False]
