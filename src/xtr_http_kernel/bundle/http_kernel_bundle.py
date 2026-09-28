"""The xtr-http-kernel bundle: the request lifecycle, under the container.

The bundle is the integration, never the library: an application drives the
lifecycle itself with :func:`xtr_http_kernel.setup`, and lists this bundle so
the container owns the pieces the lifecycle reaches for.

It contributes no services yet — it names the bundle and binds its config, so
an application can list and configure it — and boots at zero configuration.
"""

from __future__ import annotations

from typing import final

from xtr_dependency_injection import Bundle, as_bundle

from .http_kernel_config import HttpKernelConfig

__all__ = ["HttpKernelBundle"]


@final
@as_bundle("http_kernel", config=HttpKernelConfig)
class HttpKernelBundle(Bundle[HttpKernelConfig]):
    """Puts the request lifecycle's services under the container."""
