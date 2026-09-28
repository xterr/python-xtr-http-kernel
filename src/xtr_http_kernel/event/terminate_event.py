"""Dispatched last, once the response has been sent."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from starlette.requests import Request

__all__ = ["TerminateEvent"]


@final
class TerminateEvent(Event):
    """Everything was sent, or the failure went past the lifecycle.

    Dispatched after the last chunk of the response left, so nothing a
    listener does here can reach the client. That is the point: work worth
    doing once the caller has their answer — a metric, a notification, a
    write that would otherwise have held the response — belongs here.

    :attr:`status_code` is what was actually sent. When nothing was sent at
    all, because an exception left the lifecycle before the response started,
    it is ``500``: that is what the caller ends up seeing, and a listener
    counting statuses should count it.
    """

    def __init__(self, request: Request, status_code: int) -> None:
        """Announce that ``request`` was answered with ``status_code``."""
        self._request = request
        self._status_code = status_code

    @property
    def request(self) -> Request:
        """Return the request that was answered."""
        return self._request

    @property
    def status_code(self) -> int:
        """Return the status that was sent, or ``500`` when nothing was."""
        return self._status_code
