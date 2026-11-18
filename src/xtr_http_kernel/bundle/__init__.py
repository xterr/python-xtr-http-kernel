"""The xtr-dependency-injection bundle for xtr-http-kernel."""

from __future__ import annotations

from .http_kernel_bundle import HttpKernelBundle
from .http_kernel_config import HttpKernelConfig
from .profiler_config import ProfilerConfig
from .profiler_pass import ProfilerPass
from .profiling_active import profiling_active
from .route_registry_pass import ROUTE_REGISTRY_PARAMETER, RouteRegistryPass

__all__ = [
    "ROUTE_REGISTRY_PARAMETER",
    "HttpKernelBundle",
    "HttpKernelConfig",
    "ProfilerConfig",
    "ProfilerPass",
    "RouteRegistryPass",
    "profiling_active",
]
