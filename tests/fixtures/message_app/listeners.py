"""A listener stamping every response, injected one included."""

from __future__ import annotations

from xtr_event_dispatcher import as_event_listener

# Read at runtime: the dispatcher keys a listener by the event it is annotated with.
from xtr_http_kernel import ResponseEvent  # noqa: TC001 — read at runtime, see above.


@as_event_listener()
def stamp_the_response(event: ResponseEvent) -> None:
    """Mark the response, wherever it came from."""
    event.headers["x-stamped"] = "yes"
