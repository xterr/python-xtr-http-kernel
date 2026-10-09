"""The kernel every served message test builds its application on.

One kernel shape for all of them: the lifecycle bundle, the fixture
application the kernel scans — the per-request audit and the response stamp —
and the bundle counting each request built as a message.
"""

from __future__ import annotations

from xtr_dependency_injection import Kernel

from tests.support.message_counting import MessageCounterBundle
from xtr_http_kernel.bundle import HttpKernelBundle

__all__ = ["message_kernel"]


def message_kernel() -> Kernel:
    """Return a kernel serving the message fixture application."""
    return Kernel(
        "tests.fixtures.message_app",
        env="test",
        bundles={HttpKernelBundle: {"all": True}, MessageCounterBundle: {"all": True}},
    )
