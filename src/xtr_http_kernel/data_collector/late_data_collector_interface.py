"""What adds to a collector's data once the whole response has left."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .profiled_request import ProfiledRequest

__all__ = ["LateDataCollectorInterface"]


@runtime_checkable
class LateDataCollectorInterface(Protocol):
    """A collector with more to keep once the response has been sent.

    Some of what a profile shows only settles after the response started:
    the total time, the log records written while the body streamed, the
    listeners of the last events. :meth:`late_collect` is called just before
    the profile is written, with what :meth:`collect` returned.
    """

    @property
    def name(self) -> str:
        """The collector's name, as its ``collect`` side declares it."""
        ...

    def late_collect(self, data: dict[str, object], profiled: ProfiledRequest) -> dict[str, object]:
        """Return ``data`` completed with what settled after the response started."""
        ...
