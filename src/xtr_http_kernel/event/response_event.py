"""Dispatched when a response is about to start leaving."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from starlette.datastructures import MutableHeaders
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["ResponseEvent"]


@final
class ResponseEvent(Event):
    """A response is about to start, and its head can still be changed.

    Dispatched once the application has decided on a status and a set of
    headers, and before either has left — a request id, a caching directive
    or a header keeping the page out of a search index belongs here.

    **The body is not here, and cannot be replaced.** A response is streamed:
    by the time the first chunk is written the head is already gone, and the
    body may be produced a chunk at a time by something that is still
    running. This event owns exactly what an application can still change at
    that point: :attr:`status_code`, which may be assigned, and
    :attr:`headers`, which may be mutated. A listener wanting to answer with
    a body of its own does so at
    :class:`~xtr_http_kernel.event.request_event.RequestEvent` or
    :class:`~xtr_http_kernel.event.exception_event.ExceptionEvent`, where
    nothing has been sent yet.
    """

    def __init__(
        self,
        request: ServerRequestInterface,
        state: MutableMapping[str, object],
        status_code: int,
        headers: MutableHeaders,
    ) -> None:
        """Announce the response to ``request``, starting with ``status_code`` and ``headers``.

        Args:
            request: The request being answered, as a message.
            state: The per-request state bag — the same one the framework's
                own request wraps — for whatever a listener kept on it.
            status_code: The status the response will start with.
            headers: The outgoing list itself, not a copy: what a listener
                writes into it is what leaves.
        """
        self._request = request
        self._state = state
        self._status_code = status_code
        self._headers = headers

    @property
    def request(self) -> ServerRequestInterface:
        """Return the request being answered, as a message."""
        return self._request

    @property
    def state(self) -> MutableMapping[str, object]:
        """Return the per-request state bag, shared with the framework's own request."""
        return self._state

    @property
    def status_code(self) -> int:
        """Return the status the response will start with."""
        return self._status_code

    @status_code.setter
    def status_code(self, status_code: int) -> None:
        """Start the response with ``status_code`` instead."""
        self._status_code = status_code

    @property
    def headers(self) -> MutableHeaders:
        """Return the outgoing headers, to read or to change in place."""
        return self._headers
