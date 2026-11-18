from __future__ import annotations

from typing import cast

from tests.support.profiling import profiled
from xtr_http_kernel.data_collector.exception_data_collector import ExceptionDataCollector


def _raise_chained() -> BaseException:
    try:
        try:
            _ = cast("dict[str, int]", {})["missing"]
        except KeyError as error:
            shelf = "kept as a local"
            message = "could not load"
            raise RuntimeError(f"{message} from {shelf}") from error
    except RuntimeError as error:
        return error
    message = "unreachable"
    raise AssertionError(message)


def test_no_exception_is_said_so() -> None:
    assert ExceptionDataCollector().collect(profiled()) == {"has_exception": False}


def test_the_exception_and_its_cause_are_kept_with_their_frames() -> None:
    data = ExceptionDataCollector().collect(profiled(status_code=500, exception=_raise_chained()))

    chain = cast("list[dict[str, object]]", data["chain"])
    assert data["has_exception"] is True
    assert data["status_code"] == 500
    assert [error["class"] for error in chain] == ["RuntimeError", "KeyError"]
    assert chain[0]["message"] == "could not load from kept as a local"
    frame = cast("list[dict[str, object]]", chain[0]["frames"])[-1]
    assert frame["function"] == "_raise_chained"
    assert frame["file"] == __file__
    assert "shelf" in cast("dict[str, object]", frame["locals"])
    lines = cast("list[dict[str, object]]", frame["code"])
    assert any("raise RuntimeError" in cast("str", line["text"]) for line in lines)


def test_a_context_the_raise_suppressed_is_left_out() -> None:
    caught: BaseException | None = None
    try:
        try:
            _ = 1 / 0
        except ZeroDivisionError:
            message = "replaced"
            raise ValueError(message) from None
    except ValueError as error:
        caught = error

    assert caught is not None
    data = ExceptionDataCollector().collect(profiled(exception=caught))

    chain = cast("list[dict[str, object]]", data["chain"])
    assert [error["class"] for error in chain] == ["ValueError"]
    assert ExceptionDataCollector().name == "exception"


def test_an_exception_of_a_module_is_named_with_it() -> None:
    class LocalError(Exception):
        pass

    data = ExceptionDataCollector().collect(profiled(exception=LocalError("x")))

    chain = cast("list[dict[str, object]]", data["chain"])
    assert chain[0]["class"] == f"{__name__}.{LocalError.__qualname__}"
    assert chain[0]["frames"] == []
