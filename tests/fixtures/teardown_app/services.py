"""A scoped service whose cleanup fails, and a listener answering a request's failure on demand."""

from __future__ import annotations

from collections.abc import (
    AsyncIterator,  # noqa: TC003 — the container reads the factory's return type
)
from typing import final

from starlette.responses import PlainTextResponse
from xtr_dependency_injection import as_service
from xtr_event_dispatcher import as_event_listener

# Read at runtime: the dispatcher keys a listener by the event it is annotated with.
from xtr_http_kernel import ExceptionEvent  # noqa: TC001 — read at runtime, see above

__all__ = ["ANSWER_FAILURES", "Fragile", "answer_failures", "fragile"]

ANSWER_FAILURES: list[bool] = [False]
"""Whether the listener answers a request's failure — set by a test before serving."""


@final
class Fragile:
    """Built for the request; its cleanup raises."""


@as_service(lifetime="scoped")
async def fragile() -> AsyncIterator[Fragile]:
    try:
        yield Fragile()
    finally:
        raise RuntimeError("closing failed")


@as_event_listener()
async def answer_failures(event: ExceptionEvent) -> None:
    if ANSWER_FAILURES[0]:
        event.set_response(PlainTextResponse("answered", status_code=418))
