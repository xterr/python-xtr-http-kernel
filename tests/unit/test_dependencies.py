"""What the manifest says this package needs in order to run.

A package the bridge calls into on an ordinary request has to be declared as
a dependency, not merely installed here: a development group is not shipped,
so a requirement left there works in this checkout and fails in an
application.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterable

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"

_MULTIPART_PARSER = "python-multipart"


def _manifest() -> dict[str, object]:
    """Return the manifest of this package, as it is written."""
    return cast("dict[str, object]", tomllib.loads(PYPROJECT.read_text(encoding="utf-8")))


def _names(requirements: Iterable[str]) -> set[str]:
    """Return the package each requirement names, without its version or its extras."""
    return {requirement.split(">", 1)[0].split("[", 1)[0].strip() for requirement in requirements}


def _required() -> set[str]:
    """Return the name of every package this one needs in order to run."""
    project = cast("dict[str, object]", _manifest()["project"])

    return _names(cast("list[str]", project["dependencies"]))


def _for_development() -> set[str]:
    """Return the name of every package only this checkout installs."""
    groups = cast("dict[str, list[str]]", _manifest()["dependency-groups"])

    return _names(groups["dev"])


@pytest.mark.skipif(not PYPROJECT.is_file(), reason="not a source checkout")
def test_the_multipart_parser_a_submitted_form_is_read_with_is_needed_to_run() -> None:
    # The bridge asks the framework for the form behind every multipart body,
    # on any route that takes the request as a message, and the framework
    # refuses outright when the parser is missing.
    assert _MULTIPART_PARSER in _required()


@pytest.mark.skipif(not PYPROJECT.is_file(), reason="not a source checkout")
def test_the_multipart_parser_is_declared_once() -> None:
    assert _MULTIPART_PARSER not in _for_development()
