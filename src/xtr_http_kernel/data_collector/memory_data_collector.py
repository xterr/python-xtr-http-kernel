"""How much memory the process had used at its peak."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from .profiled_request import ProfiledRequest

__all__ = ["MemoryDataCollector"]

_NAME: Final = "memory"
_KIBIBYTE: Final = 1024


@final
class MemoryDataCollector:
    """Keeps the peak resident memory of the process serving the request.

    The figure is the process's, not the request's: one process serves many
    requests at once, and memory is not counted per request. It is read again
    once the response has left, since the peak may have grown meanwhile. Where
    the platform does not report it, it is ``None``.
    """

    __slots__ = ()

    @property
    def name(self) -> str:
        """``"memory"``."""
        return _NAME

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        """Return the process's peak memory so far, in bytes."""
        del profiled
        return {"peak_bytes": _peak_bytes(), "scope": "process"}

    def late_collect(self, data: dict[str, object], profiled: ProfiledRequest) -> dict[str, object]:
        """Return the peak again, read once everything was sent."""
        del profiled
        return {**data, "peak_bytes": _peak_bytes()}


def _peak_bytes() -> int | None:
    try:
        import resource  # noqa: PLC0415 — absent on some platforms, so read where it is used
    except ImportError:  # pragma: no cover — only where the platform lacks it
        return None
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes; Linux and the BSDs report kibibytes.
    return peak if sys.platform == "darwin" else peak * _KIBIBYTE
