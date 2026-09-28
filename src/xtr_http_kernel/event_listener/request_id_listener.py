"""Every request gets an id, and every response says which one it carried."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final, final
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_logging_contracts import Context

    from xtr_http_kernel.event import RequestEvent, ResponseEvent

__all__ = ["RequestIdListener"]

_VALID_REQUEST_ID: Final = re.compile(r"[A-Za-z0-9._-]{1,200}")
"""What an incoming id may look like before it is worth keeping."""

# Binding the id to the ambient log context is a courtesy to the logging
# package, which is an optional extra: without it there is nothing to bind to
# and the listener still does its job.
_bind_context: Callable[[Context], None] | None
try:
    from xtr_logging import bind_context as _bind_context
except ImportError:  # pragma: no cover — exercised only without the logging extra.
    _bind_context = None


@final
class RequestIdListener:
    """Keeps, or mints, one id per request, and echoes it on the response.

    At the request: a well-formed incoming header is kept when trusted,
    anything else is replaced with a fresh ``uuid4().hex``. The id is put on
    ``request.state.request_id`` for whoever handles the request, and bound
    to the ambient log context when the logging package is around, so every
    record made while handling carries it.

    At the response: the id goes out under the same header, so the caller
    can quote it back.
    """

    __slots__ = ("_header", "_trust_incoming")

    def __init__(self, header: str = "X-Request-Id", trust_incoming: bool = True) -> None:
        """Read and write ``header``, keeping a valid incoming id when ``trust_incoming``."""
        self._header = header
        self._trust_incoming = trust_incoming

    def on_request(self, event: RequestEvent) -> None:
        """Settle the request's id before anything handles it."""
        incoming = event.request.headers.get(self._header)
        keep = (
            self._trust_incoming and incoming is not None and _VALID_REQUEST_ID.fullmatch(incoming)
        )
        request_id = incoming if keep and incoming is not None else uuid4().hex
        event.request.state.request_id = request_id
        if _bind_context is not None:
            _bind_context({"request_id": request_id})

    def on_response(self, event: ResponseEvent) -> None:
        """Echo the request's id on the outgoing head.

        A listener answering at the request stops that event before this
        listener's request half runs, so a response can start without an id
        having been settled; such a response goes out unmarked.
        """
        request_id = getattr(event.request.state, "request_id", None)
        if isinstance(request_id, str):
            event.headers[self._header] = request_id
