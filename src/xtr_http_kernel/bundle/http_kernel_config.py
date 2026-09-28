"""Configuration for :class:`~xtr_http_kernel.bundle.http_kernel_bundle.HttpKernelBundle`."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["HttpKernelConfig"]


@dataclass(frozen=True, slots=True)
class HttpKernelConfig:
    """What an application may change about the request lifecycle.

    It carries no fields yet: the lifecycle as it stands has nothing to
    decide, and the zero-config path is the whole of it. The type exists now
    so the bundle is configurable the day a field arrives, without an
    application having to change how it configures this package.
    """
