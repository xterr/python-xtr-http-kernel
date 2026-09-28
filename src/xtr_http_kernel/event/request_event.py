"""Dispatched first, before the application sees the request."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

__all__ = ["RequestEvent"]


@final
class RequestEvent(Event):
    """A request arrived, and nothing has looked at it yet.

    This is the one moment a listener can answer instead of the application:
    :meth:`set_response` short-circuits routing, so a cache, a maintenance
    page or a redirect never reaches an endpoint. Answering stops the event,
    because the listeners after it would be deciding about a request that has
    already been dealt with.

    A listener that only wants to read or annotate the request leaves the
    response alone; the request then carries on to the router untouched.
    """

    def __init__(self, request: Request) -> None:
        """Announce ``request``, before anything has handled it."""
        self._request = request
        self._response: Response | None = None

    @property
    def request(self) -> Request:
        """Return the request that arrived."""
        return self._request

    @property
    def response(self) -> Response | None:
        """Return the response a listener answered with, if one did."""
        return self._response

    def has_response(self) -> bool:
        """Tell whether a listener answered the request itself."""
        return self._response is not None

    def set_response(self, response: Response) -> None:
        """Answer the request with ``response``, and skip the listeners after this one.

        The application never runs: ``response`` is what leaves, after the
        rest of the lifecycle has had its say about it.
        """
        self._response = response
        self.stop_propagation()
