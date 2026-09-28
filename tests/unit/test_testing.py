"""The override seam: a mapping parked on the application until the next build."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi import FastAPI

from xtr_http_kernel.testing import override_services

if TYPE_CHECKING:
    from collections.abc import Hashable

_KEY = "_xtr_http_kernel_overrides"


class Service:
    """A key to override."""


def test_the_overrides_sit_on_the_application_only_inside_the_block() -> None:
    app = FastAPI()
    replacement = object()

    with override_services(app, {Service: replacement}):
        assert getattr(app.state, _KEY) == {Service: replacement}

    assert getattr(app.state, _KEY, None) is None


def test_the_stored_mapping_is_a_copy() -> None:
    app = FastAPI()
    overrides: dict[type | tuple[type, Hashable], object] = {Service: object()}

    with override_services(app, overrides):
        overrides[(Service, "late")] = object()

        stored = cast("dict[object, object]", getattr(app.state, _KEY))
        assert list(stored) == [Service]


def test_nested_blocks_restore_the_previous_overrides() -> None:
    app = FastAPI()
    first = object()
    second = object()

    with override_services(app, {Service: first}):
        with override_services(app, {Service: second}):
            assert getattr(app.state, _KEY) == {Service: second}

        assert getattr(app.state, _KEY) == {Service: first}

    assert getattr(app.state, _KEY, None) is None
