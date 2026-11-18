"""Whether requests are profiled, as another bundle asks it before registering a collector."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_dependency_injection import bundle_active

from .http_kernel_config import HttpKernelConfig

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder

__all__ = ["profiling_active"]


def profiling_active(builder: ContainerBuilder) -> bool:
    """Tell whether the http kernel's bundle is active with its profiler on.

    A library's bundle registers its data collector only then, from its
    ``load_extension`` — every bundle's configuration is resolved before any is
    loaded, so the answer holds whatever order the bundles load in:

    ```python
    if bundle_active(builder, "http_kernel"):
        from xtr_http_kernel.bundle import profiling_active

        if profiling_active(builder):
            register_collector(services)
    ```
    """
    if not bundle_active(builder, "http_kernel"):
        return False
    return builder.get_extension_config(HttpKernelConfig).profiler.enabled
