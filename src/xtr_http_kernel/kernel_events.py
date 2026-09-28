"""The names the request lifecycle dispatches its events under."""

from __future__ import annotations

from typing import Final, final

from xtr_event_dispatcher_contracts import event_name_of

from .event import (
    ExceptionEvent,
    FinishRequestEvent,
    RequestEvent,
    ResponseEvent,
    TerminateEvent,
)

__all__ = ["KernelEvents"]


@final
class KernelEvents:
    """One name per lifecycle event, for listeners registered by name.

    An event is keyed by the qualified name of its class, so a listener
    declared on a typed parameter and one registered under the matching
    constant here are registered for the same event. The constants exist for
    the places a class cannot be written — a listener whose event is chosen
    at runtime, a configuration file, a subscriber mapping names to methods:

    ```python
    dispatcher.add_listener(KernelEvents.RESPONSE, stamp_request_id, priority=100)
    ```

    Keeping them in one place also means the set of moments a request goes
    through can be read at a glance, in the order it goes through them.
    """

    REQUEST: Final[str] = event_name_of(RequestEvent)
    """The request arrived and nothing has handled it."""

    RESPONSE: Final[str] = event_name_of(ResponseEvent)
    """A response is about to start, and its head can still be changed."""

    EXCEPTION: Final[str] = event_name_of(ExceptionEvent)
    """Handling raised, and nothing has been sent."""

    FINISH_REQUEST: Final[str] = event_name_of(FinishRequestEvent)
    """Handling finished — dispatched on every path."""

    TERMINATE: Final[str] = event_name_of(TerminateEvent)
    """Everything has been sent, or the failure went past the lifecycle."""
