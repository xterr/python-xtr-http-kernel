"""Listeners journaling the lifecycle, for the served-request acceptance suite.

Each journals what it saw into a list a test reads back, and the request
listener is the one a test steers: whether it reads the served request's
body — the case the replay receive exists for — and whether it answers
instead of the application, are both module-level settings the test sets
before serving.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from xtr_event_dispatcher import as_event_listener

# Read at runtime: the dispatcher keys a listener by the event it is annotated with.
from xtr_http_kernel import (  # noqa: TC001 — read at runtime, see above
    ExceptionEvent,
    FinishRequestEvent,
    RequestEvent,
    ResponseEvent,
    TerminateEvent,
)

if TYPE_CHECKING:
    from starlette.responses import Response

__all__ = [
    "ANSWER",
    "BODIES",
    "LIFECYCLE",
    "READ_BODY",
    "SEEN",
]

READ_BODY: bool = False
"""Whether the request listener reads the body — set by a test before serving."""

ANSWER: Response | None = None
"""The response the request listener answers with — set by a test before serving."""

SEEN: Final[list[str]] = []
"""The path of every request event, in order."""

BODIES: Final[list[bytes]] = []
"""Every body the request listener read, in order."""

LIFECYCLE: Final[list[tuple[str, int]]] = []
"""Every lifecycle event, as its name and the identity of the request it carried."""


@as_event_listener()
async def watch_the_request(event: RequestEvent) -> None:
    """Journal the request, reading its body only when a test asks it to."""
    LIFECYCLE.append(("request", id(event.request)))
    SEEN.append(event.request.get_uri().get_path())
    if READ_BODY:
        BODIES.append(await event.request.get_body().get_contents())
    if ANSWER is not None:
        event.set_response(ANSWER)


@as_event_listener()
async def watch_the_response(event: ResponseEvent) -> None:
    """Journal the response event's request."""
    LIFECYCLE.append(("response", id(event.request)))


@as_event_listener()
async def watch_the_exception(event: ExceptionEvent) -> None:
    """Journal the exception event's request."""
    LIFECYCLE.append(("exception", id(event.request)))


@as_event_listener()
async def watch_the_finish(event: FinishRequestEvent) -> None:
    """Journal the finish event's request."""
    LIFECYCLE.append(("finish", id(event.request)))


@as_event_listener()
async def watch_the_terminate(event: TerminateEvent) -> None:
    """Journal the terminate event's request."""
    LIFECYCLE.append(("terminate", id(event.request)))
