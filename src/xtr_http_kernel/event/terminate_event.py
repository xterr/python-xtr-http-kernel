"""Dispatched last, once the response has been sent."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from xtr_http_message_contracts import ServerRequestInterface

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

    def __init__(
        self,
        request: ServerRequestInterface,
        state: MutableMapping[str, object],
        status_code: int,
    ) -> None:
        """Announce that ``request`` was answered with ``status_code``.

        Args:
            request: The request that was answered, as a message.
            state: The per-request state bag — the same one the framework's
                own request wraps — for whatever a listener kept on it.
            status_code: The status that was sent, or ``500`` when nothing
                was.
        """
        self._request = request
        self._state = state
        self._status_code = status_code

    @property
    def request(self) -> ServerRequestInterface:
        """Return the request that was answered, as a message."""
        return self._request

    @property
    def state(self) -> MutableMapping[str, object]:
        """Return the per-request state bag, shared with the framework's own request."""
        return self._state

    @property
    def status_code(self) -> int:
        """Return the status that was sent, or ``500`` when nothing was."""
        return self._status_code
