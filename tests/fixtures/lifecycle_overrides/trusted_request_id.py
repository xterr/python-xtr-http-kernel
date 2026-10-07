"""Trusts an inbound request id, for the kernels that scan this module."""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_http_kernel.bundle import HttpKernelConfig


@configure
def http_kernel() -> HttpKernelConfig:
    return HttpKernelConfig(trust_request_id=True)
