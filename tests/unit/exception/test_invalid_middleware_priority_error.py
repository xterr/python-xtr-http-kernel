"""The error a non-integer middleware priority fails the build with."""

from __future__ import annotations

from xtr_http_kernel import HttpKernelError
from xtr_http_kernel.exception import InvalidMiddlewarePriorityError


class _Factory:
    """A stand-in for a tagged middleware factory."""


def test_it_derives_from_the_package_base_error() -> None:
    error = InvalidMiddlewarePriorityError((_Factory, None), "high")

    assert isinstance(error, HttpKernelError)


def test_it_carries_the_key_and_the_priority_as_attributes() -> None:
    error = InvalidMiddlewarePriorityError((_Factory, None), "high")

    assert error.key == (_Factory, None)
    assert error.priority == "high"


def test_the_message_names_the_service_and_the_offending_priority() -> None:
    error = InvalidMiddlewarePriorityError((_Factory, None), "high")

    assert f"{_Factory.__module__}.{_Factory.__qualname__}" in str(error)
    assert "'high'" in str(error)


def test_the_message_carries_the_qualifier_when_there_is_one() -> None:
    error = InvalidMiddlewarePriorityError((_Factory, "outer"), 1.5)

    assert "['outer']" in str(error)
    assert "1.5" in str(error)
