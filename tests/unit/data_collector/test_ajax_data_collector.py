from __future__ import annotations

from tests.support.profiling import profiled
from xtr_http_kernel.data_collector.ajax_data_collector import AjaxDataCollector


def test_nothing_is_kept() -> None:
    collector = AjaxDataCollector()

    assert collector.collect(profiled()) == {}
    assert collector.name == "ajax"
