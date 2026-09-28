"""Each request framed as one unit of work for the logging package.

This module needs the optional logging extra: it is deliberately left out of
the package's eager re-exports, and the bundle registers the listener only
when the logging bundle is active.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_logging import begin_unit, end_unit

if TYPE_CHECKING:
    from xtr_http_kernel.event import RequestEvent, TerminateEvent

__all__ = ["LogUnitListener"]


@final
class LogUnitListener:
    """Opens a unit of work when a request arrives, and closes it when all was sent.

    State the logging package keeps per unit — the id tying a request's
    records together, a fingers-crossed buffer — then lives exactly as long
    as the request, and two requests handled at once keep their own.
    """

    __slots__ = ()

    def on_request(self, event: RequestEvent) -> None:
        """Open the request's unit, before anything else contributes."""
        del event
        begin_unit()

    def on_terminate(self, event: TerminateEvent) -> None:
        """Close the unit, after everything has been sent."""
        del event
        end_unit()
