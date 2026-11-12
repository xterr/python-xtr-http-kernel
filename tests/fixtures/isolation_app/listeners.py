"""A listener reading each request before routing, the way a step deciding there does."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, final

from starlette.datastructures import FormData
from xtr_dependency_injection.exception import FastapiIntegrationError
from xtr_dependency_injection.integration.fastapi import current_connection
from xtr_event_dispatcher import as_event_listener
from xtr_logging import current_context

# Read at runtime: the dispatcher keys a listener by the event it is annotated with.
from xtr_http_kernel import RequestEvent  # noqa: TC001 — read at runtime, see above.


@final
@dataclass(frozen=True, slots=True)
class Reading:
    """What the listener found when one request arrived."""

    path: str
    published: str | None
    """The path of the connection already published when the request arrived, if one was."""
    title: object
    """The ``title`` field of the form the request's own message answered."""


READ: Final[list[Reading]] = []
"""One reading per request, in the order the requests arrived."""

CUSTOMERS: Final[list[object]] = []
"""The ``customer`` key each request found bound in the log context as it arrived."""


@as_event_listener()
async def read_the_request(event: RequestEvent) -> None:
    """Read the body through the request's message, and journal what it answered."""
    request = event.request
    CUSTOMERS.append(current_context().get("customer"))
    try:
        published: str | None = current_connection().url.path
    except FastapiIntegrationError:
        published = None
    _ = await request.get_body().get_contents()
    form = request.get_parsed_body()
    title = form.get("title") if isinstance(form, FormData) else None
    READ.append(Reading(request.get_uri().get_path(), published, title))
