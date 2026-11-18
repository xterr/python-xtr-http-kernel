"""How long the request took, and where the time went."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from xtr_clock import SystemClock
from xtr_stopwatch import SECTION_EVENT

from xtr_http_kernel.profiler import _state_keys as keys

if TYPE_CHECKING:
    from xtr_clock import ClockInterface
    from xtr_stopwatch import Stopwatch

    from .profiled_request import ProfiledRequest

__all__ = ["TimeDataCollector"]

_NAME: Final = "time"
_MILLISECONDS_PER_SECOND: Final = 1000.0


@final
class TimeDataCollector:
    """Keeps the request's duration and every event its stopwatch section timed.

    The duration at the response start is kept first; once everything has
    been sent, the section's own events replace it — the whole request, body
    included — together with each event the section holds, as plain data a
    timeline is drawn from.
    """

    __slots__ = ("_clock", "_stopwatch")

    def __init__(self, stopwatch: Stopwatch, clock: ClockInterface | None = None) -> None:
        """Read the request's section from ``stopwatch``.

        Args:
            stopwatch: Where each request's section is timed.
            clock: What "now" is read from; :class:`~xtr_clock.SystemClock` by
                default, the clock the arrival was read from.
        """
        self._stopwatch = stopwatch
        self._clock: ClockInterface = clock if clock is not None else SystemClock()

    @property
    def name(self) -> str:
        """``"time"``."""
        return _NAME

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        """Return when the request arrived and how long it took until its response started."""
        start = profiled.state.get(keys.START)
        if not isinstance(start, float):
            return {"start_time": None, "duration_ms": None, "events": {}}
        elapsed = (self._clock.now().timestamp() - start) * _MILLISECONDS_PER_SECOND
        return {"start_time": start, "duration_ms": elapsed, "events": {}}

    def late_collect(self, data: dict[str, object], profiled: ProfiledRequest) -> dict[str, object]:
        """Return the section's events, and the whole request's duration from its section."""
        token = profiled.state.get(keys.TOKEN)
        if not isinstance(token, str):
            return data
        events = self._stopwatch.get_section_events(token)
        section = events.get(SECTION_EVENT)
        return {
            **data,
            "duration_ms": section.get_duration() if section is not None else data["duration_ms"],
            "origin": section.origin if section is not None else None,
            "events": {name: event.to_dict() for name, event in events.items()},
        }
