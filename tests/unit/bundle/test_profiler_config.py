from __future__ import annotations

import pytest

from xtr_http_kernel.bundle import HttpKernelConfig, ProfilerConfig
from xtr_http_kernel.exception import InvalidArgumentError


def test_profiling_is_off_by_default() -> None:
    assert ProfilerConfig().enabled is False
    assert HttpKernelConfig().profiler == ProfilerConfig()


def test_the_profilers_own_pages_are_excluded_by_default() -> None:
    assert ProfilerConfig().excluded_paths == ("^/_(wdt|profiler)",)


def test_an_excluded_path_that_is_no_regular_expression_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="not a regular expression"):
        _ = ProfilerConfig(excluded_paths=("(",))


def test_an_empty_collect_parameter_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="collect_parameter"):
        _ = ProfilerConfig(collect_parameter="")


def test_a_lifetime_below_one_second_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="lifetime_seconds"):
        _ = ProfilerConfig(lifetime_seconds=0)
