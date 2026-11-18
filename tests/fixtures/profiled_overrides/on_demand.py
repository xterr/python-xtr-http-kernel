"""Profiles only the requests asking for it with ``?profile=1``."""

from __future__ import annotations

import os

from xtr_dependency_injection import configure

from xtr_http_kernel.bundle import HttpKernelConfig, ProfilerConfig


@configure
def http_kernel() -> HttpKernelConfig:
    return HttpKernelConfig(
        profiler=ProfilerConfig(
            enabled=True,
            collect=False,
            collect_parameter="profile",
            storage_path=os.environ["PROFILER_TEST_FOLDER"],
        )
    )
