"""What a routes file records and replays, in the order it wrote it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_kernel.routing.route_collection import RouteCollection

__all__ = ["StepInterface"]


@runtime_checkable
class StepInterface(Protocol):
    """One thing a routes file asked for, applied to the table when the file returns."""

    def apply_to(self, collection: RouteCollection) -> None:
        """Make the change on ``collection``."""
        ...
