from __future__ import annotations

from typing import cast

from tests.support.profiling import profiled
from xtr_http_kernel.data_collector.config_data_collector import ConfigDataCollector


def test_the_runtime_and_the_kernel_are_kept() -> None:
    collector = ConfigDataCollector(
        "dev", debug=True, bundles={"http_kernel": "xtr.HttpKernelBundle"}
    )

    data = collector.collect(profiled())
    again = collector.collect(profiled())

    assert data["environment"] == "dev"
    assert data["debug"] is True
    assert data["bundles"] == {"http_kernel": "xtr.HttpKernelBundle"}
    assert "xtr-http-kernel" in cast("dict[str, str]", data["packages"])
    assert data["server"] == ["shop.test", "80"]
    assert again["packages"] == data["packages"]
    assert collector.name == "config"
