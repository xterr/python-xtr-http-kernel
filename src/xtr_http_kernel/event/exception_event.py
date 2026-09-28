"""Dispatched when handling a request raised."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

__all__ = ["ExceptionEvent"]


@final
class ExceptionEvent(Event):
    """Handling ``request`` raised, and nothing has been sent.

    A listener that only wants to know — one writing the failure to a log,
    say — reads :attr:`exception` and leaves the response alone: the
    exception then carries on out of the lifecycle, to whatever the
    application put in charge of turning it into a response.

    A listener that wants to answer calls :meth:`set_response`, which stops
    the event: the exception is swallowed, and that response leaves instead.

    :attr:`exception` is a :class:`BaseException`, not an :class:`Exception`:
    a cancellation or an interrupt is exactly the kind of failure a listener
    logging what went wrong wants to see.
    """

    def __init__(self, request: Request, exception: BaseException) -> None:
        """Announce that handling ``request`` raised ``exception``."""
        self._request = request
        self._exception = exception
        self._response: Response | None = None

    @property
    def request(self) -> Request:
        """Return the request whose handling raised."""
        return self._request

    @property
    def exception(self) -> BaseException:
        """Return what was raised."""
        return self._exception

    @property
    def response(self) -> Response | None:
        """Return the response a listener turned the exception into, if one did."""
        return self._response

    def has_response(self) -> bool:
        """Tell whether a listener turned the exception into a response."""
        return self._response is not None

    def set_response(self, response: Response) -> None:
        """Answer with ``response``, and skip the listeners after this one.

        The exception stops here: ``response`` is what leaves, and the
        listeners that have not run never hear about the failure.
        """
        self._response = response
        self.stop_propagation()
