"""The xtr-dependency-injection bundle for xtr-http-kernel."""

from __future__ import annotations

from .http_kernel_bundle import HttpKernelBundle
from .http_kernel_config import HttpKernelConfig
from .routing_resolver_pass import ROUTE_TABLE_PARAMETER, RoutingResolverPass

__all__ = ["ROUTE_TABLE_PARAMETER", "HttpKernelBundle", "HttpKernelConfig", "RoutingResolverPass"]
