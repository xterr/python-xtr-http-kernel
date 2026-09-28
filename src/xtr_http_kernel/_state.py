"""Where the setup call, its middleware and the test seam meet: the app's state.

Kept apart so the middleware module shares these keys with the setup and
testing modules without importing either.
"""

from __future__ import annotations

from typing import Final

__all__ = ["FACTORIES_KEY", "OVERRIDES_KEY"]

FACTORIES_KEY: Final = "_xtr_http_kernel_middleware"
"""Where each application life parks the composed chain's factories."""

OVERRIDES_KEY: Final = "_xtr_http_kernel_overrides"
"""Where :func:`xtr_http_kernel.testing.override_services` parks its mapping."""
