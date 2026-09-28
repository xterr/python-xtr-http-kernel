"""Dispatched when handling of a request finished, whatever came of it."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from starlette.requests import Request

__all__ = ["FinishRequestEvent"]


@final
class FinishRequestEvent(Event):
    """Handling of ``request`` finished — the one event dispatched on every path.

    It runs whether the application answered, a listener short-circuited the
    request, an exception was turned into a response, or an exception is
    about to leave the lifecycle unhandled. That is what makes it the place
    to put away anything a request set up: the per-request logging unit, a
    trace, a scope closed by hand.

    When there is a body, it is dispatched before the last chunk leaves, so a
    listener can still do its work while the request is recognisably the one
    being answered. It carries no response: by this point the head is gone,
    and there is nothing left to change — see
    :class:`~xtr_http_kernel.event.terminate_event.TerminateEvent` for what
    was actually sent.
    """

    def __init__(self, request: Request) -> None:
        """Announce that handling ``request`` finished."""
        self._request = request

    @property
    def request(self) -> Request:
        """Return the request whose handling finished."""
        return self._request
