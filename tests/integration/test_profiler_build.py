"""The profiler's wiring, through a real kernel: collectors from any bundle, in priority order."""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

import pytest
from xtr_dependency_injection import Bundle, Kernel, as_bundle

from xtr_http_kernel.bundle import HttpKernelBundle
from xtr_http_kernel.data_collector import DATA_COLLECTOR_TAG, DataCollectorTemplates
from xtr_http_kernel.exception import InvalidCollectorPriorityError, InvalidCollectorTagError
from xtr_http_kernel.profiler import Profiler

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

    from xtr_http_kernel.data_collector import ProfiledRequest

pytestmark = pytest.mark.anyio


@final
class _BooksCollector:
    @property
    def name(self) -> str:
        return "books"

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        del profiled
        return {"books": 3}


def books_collector() -> _BooksCollector:
    return _BooksCollector()


@as_bundle("books")
class BooksBundle(Bundle):
    """Tags one collector of its own, between the request and the time panels."""

    @override
    def load_extension(
        self, config: object, services: ServiceConfigurator, builder: ContainerBuilder
    ) -> None:
        del config, builder
        _ = services.set(books_collector).add_tag(
            DATA_COLLECTOR_TAG, name="books", template="@books/books.html.j2", priority=332
        )


@as_bundle("nameless")
class NamelessBundle(Bundle):
    """Tags a collector without the name the profile keeps it under."""

    @override
    def load_extension(
        self, config: object, services: ServiceConfigurator, builder: ContainerBuilder
    ) -> None:
        del config, builder
        _ = services.set(books_collector).add_tag(DATA_COLLECTOR_TAG, template="@books/b.html.j2")


@as_bundle("templateless")
class TemplatelessBundle(Bundle):
    """Tags a collector without the template its panel is shown with."""

    @override
    def load_extension(
        self, config: object, services: ServiceConfigurator, builder: ContainerBuilder
    ) -> None:
        del config, builder
        _ = services.set(books_collector).add_tag(DATA_COLLECTOR_TAG, name="books")


@as_bundle("bad_collector_priority")
class BadPriorityBundle(Bundle):
    """Tags a collector with a priority no integer can be read from."""

    @override
    def load_extension(
        self, config: object, services: ServiceConfigurator, builder: ContainerBuilder
    ) -> None:
        del config, builder
        _ = services.set(books_collector).add_tag(
            DATA_COLLECTOR_TAG, name="books", template="@books/b.html.j2", priority="high"
        )


@pytest.fixture(autouse=True)
def _folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROFILER_TEST_FOLDER", str(tmp_path))


def _kernel(contributor: type[Bundle]) -> Kernel:
    return Kernel(
        "xtr_http_kernel.bundle",
        env="test",
        bundles={contributor: {"all": True}, HttpKernelBundle: {"all": True}},
        resources=("tests.fixtures.profiled_overrides.enabled",),
    )


async def test_a_bundles_collector_joins_the_core_ones_in_priority_order() -> None:
    async with await _kernel(BooksBundle).boot() as booted:
        profiler = await booted.container.get(Profiler)
        templates = await booted.container.get(DataCollectorTemplates)

    names = [collector.name for collector in profiler.all()]
    assert names[:3] == ["request", "books", "time"]
    assert names[-1] == "config"
    assert templates.template_of("books") == "@books/books.html.j2"
    assert templates.template_of("request") == "@xtr_web_profiler/collector/request.html.j2"
    assert [name for name, _ in templates.entries] == names


def test_a_collector_tagged_without_a_name_fails_the_build() -> None:
    with pytest.raises(InvalidCollectorTagError, match="'name'"):
        _ = _kernel(NamelessBundle).build()


def test_a_collector_tagged_without_a_template_fails_the_build() -> None:
    with pytest.raises(InvalidCollectorTagError, match="'template'"):
        _ = _kernel(TemplatelessBundle).build()


def test_a_non_integer_collector_priority_fails_the_build() -> None:
    with pytest.raises(InvalidCollectorPriorityError, match="'high'"):
        _ = _kernel(BadPriorityBundle).build()
