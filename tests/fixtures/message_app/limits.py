"""Lets the fixture application read any body: its tests measure buffering, not the limit."""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_http_kernel.bundle import HttpKernelConfig

__all__ = ["http_kernel"]


@configure
def http_kernel() -> HttpKernelConfig:
    return HttpKernelConfig(max_body_size=None)
