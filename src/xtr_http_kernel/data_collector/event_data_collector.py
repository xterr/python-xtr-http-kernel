"""Which listeners the request's events reached, and which they did not."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from xtr_event_dispatcher.debug import TraceableEventDispatcher

if TYPE_CHECKING:
    from xtr_event_dispatcher import EventDispatcherInterface
    from xtr_event_dispatcher.debug import ListenerInfo

    from .profiled_request import ProfiledRequest

__all__ = ["EventDataCollector"]

_NAME: Final = "events"


@final
class EventDataCollector:
    """Keeps the listeners called, the ones not called and the events nobody heard.

    Read off a traced dispatcher once everything has been sent, so the last
    events of the request are in. The trace is per unit of work, so it holds
    this request's events alone. A dispatcher that is not traced — outside
    debug mode — has nothing to read, and the panel says so.
    """

    __slots__ = ("_dispatcher",)

    def __init__(self, dispatcher: EventDispatcherInterface) -> None:
        """Read what ``dispatcher`` traced."""
        self._dispatcher = dispatcher

    @property
    def name(self) -> str:
        """``"events"``."""
        return _NAME

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        """Return nothing yet; the trace is read once the response has left."""
        del profiled
        return {"traced": isinstance(self._dispatcher, TraceableEventDispatcher)}

    def late_collect(self, data: dict[str, object], profiled: ProfiledRequest) -> dict[str, object]:
        """Return the called and not-called listeners, and the orphaned events."""
        del profiled
        dispatcher = self._dispatcher
        if not isinstance(dispatcher, TraceableEventDispatcher):
            return data
        return {
            **data,
            "called": [_info(info) for info in dispatcher.get_called_listeners()],
            "not_called": [_info(info) for info in dispatcher.get_not_called_listeners()],
            "orphaned": dispatcher.get_orphaned_events(),
        }


def _info(info: ListenerInfo) -> dict[str, object]:
    return {
        "event": info.event,
        "priority": info.priority,
        "listener": info.pretty,
        "calls": info.calls,
        "duration_ms": info.duration * 1000.0,
    }
