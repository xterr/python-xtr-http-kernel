"""Unit tests for :class:`xtr_http_kernel.command.OpenApiExportCommand`."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING, cast

import pytest
import yaml
from xtr_console import ExitCode

from tests.fixtures.openapi_app.app import app as described_app
from xtr_http_kernel.bundle import HttpKernelConfig
from xtr_http_kernel.command import OpenApiExportCommand

if TYPE_CHECKING:
    import io as streams
    from pathlib import Path

    from xtr_console import ApplicationTester, ConsoleStyle

pytestmark = pytest.mark.anyio

APPLICATION = "tests.fixtures.openapi_app.app:app"

type Document = dict[str, object]


def _document(text: str) -> Document:
    return cast("Document", json.loads(text))


def _schemas(document: Document) -> Document:
    return cast("Document", cast("Document", document["components"])["schemas"])


def _paths(document: Document) -> Document:
    return cast("Document", document["paths"])


async def _export(tester: ApplicationTester, *options: str) -> Document:
    code = await tester.execute(["api:openapi:export", "--app", APPLICATION, *options])
    assert code == ExitCode.SUCCESS, tester.display
    return _document(tester.display)


async def test_it_writes_the_description_the_application_serves_as_json(
    tester: ApplicationTester,
) -> None:
    exported = await _export(tester)

    assert exported == described_app.openapi()


async def test_the_description_keeps_its_text_as_written(tester: ApplicationTester) -> None:
    _ = await _export(tester)

    assert "Le catalogue — livres et commandes" in tester.display


async def test_yaml_writes_the_same_description(tester: ApplicationTester) -> None:
    code = await tester.execute(["api:openapi:export", "--app", APPLICATION, "-y"])

    assert code == ExitCode.SUCCESS
    assert yaml.safe_load(tester.display) == described_app.openapi()
    assert "&id" not in tester.display


async def test_yaml_without_pyyaml_asks_for_it(
    tester: ApplicationTester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "yaml", None)

    code = await tester.execute(["api:openapi:export", "--app", APPLICATION, "--yaml"])

    assert code == ExitCode.FAILURE
    assert "PyYAML" in tester.display
    assert "xtr-http-kernel[yaml]" in " ".join(tester.display.split())


async def test_output_writes_the_description_to_a_file(
    tester: ApplicationTester, tmp_path: Path
) -> None:
    target = tmp_path / "openapi.json"

    code = await tester.execute(["api:openapi:export", "--app", APPLICATION, "-o", str(target)])

    assert code == ExitCode.SUCCESS
    assert _document(target.read_text(encoding="utf-8")) == described_app.openapi()
    assert "Data written to" in tester.display


async def test_an_output_it_cannot_write_fails(tester: ApplicationTester, tmp_path: Path) -> None:
    target = tmp_path / "missing" / "openapi.json"

    code = await tester.execute(["api:openapi:export", "--app", APPLICATION, "-o", str(target)])

    assert code == ExitCode.FAILURE
    assert "Cannot write" in tester.display


async def test_openapi_2_is_refused(tester: ApplicationTester) -> None:
    code = await tester.execute(["api:openapi:export", "--app", APPLICATION, "--spec-version", "2"])

    assert code == ExitCode.INVALID
    assert "OpenAPI 2 is not supported" in tester.display


async def test_filter_tags_keeps_the_operations_of_those_tags(tester: ApplicationTester) -> None:
    exported = await _export(tester, "--filter-tags", "orders")

    assert list(_paths(exported)) == ["/orders"]
    assert exported["tags"] == [{"name": "orders"}]


async def test_filter_tags_takes_several(tester: ApplicationTester) -> None:
    exported = await _export(tester, "--filter-tags", "orders", "--filter-tags", "books")

    assert set(_paths(exported)) == {"/books", "/orders"}


async def test_api_gateway_reshapes_what_a_gateway_refuses(tester: ApplicationTester) -> None:
    exported = await _export(tester, "--api-gateway")

    schemas = _schemas(exported)
    assert "PageBook" in schemas
    assert "Page_Book_" not in schemas
    book = cast("Document", cast("Document", schemas["Book"])["properties"])
    assert "readOnly" not in cast("Document", book["isbn"])
    listing = cast("Document", cast("Document", _paths(exported)["/books"])["get"])
    parameters = cast("list[Document]", listing["parameters"])
    assert [parameter["name"] for parameter in parameters] == ["page"]
    assert "#/components/schemas/PageBook" in tester.display


async def test_reshaping_leaves_the_applications_own_description_alone(
    tester: ApplicationTester,
) -> None:
    _ = await _export(tester, "--api-gateway", "--filter-tags", "orders")

    assert "Page_Book_" in _schemas(cast("Document", described_app.openapi()))


async def test_the_configured_application_needs_no_option(
    captured: tuple[ConsoleStyle, streams.StringIO],
) -> None:
    style, buffer = captured
    command = OpenApiExportCommand(HttpKernelConfig(app=APPLICATION))

    assert await command(style) == ExitCode.SUCCESS
    assert _document(buffer.getvalue())["info"] == {
        "title": "Librairie",
        "description": "Le catalogue — livres et commandes",
        "version": "0.1.0",
    }


async def test_without_an_application_it_exports_nothing(tester: ApplicationTester) -> None:
    code = await tester.execute(["api:openapi:export"])

    assert code == ExitCode.INVALID
    assert "--app" in tester.display
