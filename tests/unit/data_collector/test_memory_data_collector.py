from __future__ import annotations

from tests.support.profiling import profiled
from xtr_http_kernel.data_collector.memory_data_collector import MemoryDataCollector


def test_the_process_peak_is_kept_and_read_again_once_sent() -> None:
    collector = MemoryDataCollector()

    data = collector.late_collect(collector.collect(profiled()), profiled())

    assert data["scope"] == "process"
    assert isinstance(data["peak_bytes"], int)
    assert data["peak_bytes"] > 0
    assert collector.name == "memory"
