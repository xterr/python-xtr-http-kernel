"""Names the fixture application on the configuration, for kernels scanning this module."""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_http_kernel.bundle import HttpKernelConfig


@configure
def http_kernel() -> HttpKernelConfig:
    return HttpKernelConfig(app="tests.fixtures.router_app.app:app")
