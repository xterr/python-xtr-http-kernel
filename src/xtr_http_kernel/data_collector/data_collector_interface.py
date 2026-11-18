"""What gathers one panel's worth of a request's profile."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .profiled_request import ProfiledRequest

__all__ = ["DataCollectorInterface"]


@runtime_checkable
class DataCollectorInterface(Protocol):
    """Picks up what a request left behind, as plain data, once its response starts.

    A collector is shared by every request a process serves at once, so it
    keeps nothing of its own: :meth:`collect` *returns* the request's data,
    and the profile keeps it under :attr:`name`. What it returns must be plain
    data — mappings, lists, strings, numbers, booleans and ``None`` — because
    the profile is written as JSON; hand anything else to
    :func:`~xtr_http_kernel.data_collector.clone_var` first.

    ``collect`` is not where data is gathered, only picked up: something that
    happens while the request is handled records itself — on a traced
    service, on the request's state — and the collector reads that.
    """

    @property
    def name(self) -> str:
        """What the profile keeps this collector's data under; unique in the application."""
        ...

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        """Return what this collector keeps of ``profiled``, as plain data."""
        ...
