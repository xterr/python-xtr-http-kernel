"""The xtr-dependency-injection bundle for xtr-http-kernel."""

from __future__ import annotations

from .http_kernel_bundle import HttpKernelBundle
from .http_kernel_config import HttpKernelConfig
from .route_registry_pass import ROUTE_REGISTRY_PARAMETER, RouteRegistryPass

__all__ = ["ROUTE_REGISTRY_PARAMETER", "HttpKernelBundle", "HttpKernelConfig", "RouteRegistryPass"]
