"""A collector whose data is recorded while the request is handled, not picked up at its end."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["TracingDataCollectorInterface"]


@runtime_checkable
class TracingDataCollectorInterface(Protocol):
    """A collector told when a profiled request arrives, to start recording it.

    Its instrumentation records into a
    :class:`~xtr_http_kernel.data_collector.RequestTrace` while the request is
    handled; :meth:`begin_request` starts that trace afresh for the request,
    in the request's own context. The profiler calls it for every collector
    implementing it, once it has decided the request is profiled — an
    unprofiled request records nothing.
    """

    def begin_request(self) -> None:
        """Start recording the request that just arrived."""
        ...
