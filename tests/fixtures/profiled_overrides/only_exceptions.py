"""Profiles only the requests whose handling raised."""

from __future__ import annotations

import os

from xtr_dependency_injection import configure

from xtr_http_kernel.bundle import HttpKernelConfig, ProfilerConfig


@configure
def http_kernel() -> HttpKernelConfig:
    return HttpKernelConfig(
        profiler=ProfilerConfig(
            enabled=True, only_exceptions=True, storage_path=os.environ["PROFILER_TEST_FOLDER"]
        )
    )
