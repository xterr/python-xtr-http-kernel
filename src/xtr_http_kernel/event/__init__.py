"""The events a request goes through, from arriving to being answered.

Every request dispatches the same sequence, and a listener joins it wherever
it has something to contribute:

1. :class:`RequestEvent` — it arrived, nothing has looked at it. A listener
   may answer it here instead of the application.
2. :class:`ResponseEvent` — a response is about to start; its status and
   headers can still be changed. **Or** :class:`ExceptionEvent` — handling
   raised, and a listener may turn that into a response.
3. :class:`FinishRequestEvent` — handling finished, on every path.
4. :class:`TerminateEvent` — everything has been sent; whatever is done here
   cannot reach the caller.

Events are keyed by the qualified name of their class, so listening to
``RequestEvent`` and listening to
:data:`~xtr_http_kernel.kernel_events.KernelEvents.REQUEST` name the same
event.
"""

from __future__ import annotations

from .exception_event import ExceptionEvent
from .finish_request_event import FinishRequestEvent
from .request_event import RequestEvent
from .response_event import ResponseEvent
from .terminate_event import TerminateEvent

__all__ = [
    "ExceptionEvent",
    "FinishRequestEvent",
    "RequestEvent",
    "ResponseEvent",
    "TerminateEvent",
]
