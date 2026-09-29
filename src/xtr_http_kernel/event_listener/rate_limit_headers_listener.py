"""Responses say how much of their rate limit is left."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from xtr_http_kernel.rate_limiter._applied_rate_limit import applied_rate_limit

if TYPE_CHECKING:
    from xtr_http_kernel.event import ResponseEvent

__all__ = ["RateLimitHeadersListener"]

_LIMIT: Final = "X-RateLimit-Limit"
_REMAINING: Final = "X-RateLimit-Remaining"
_RESET: Final = "X-RateLimit-Reset"


@final
class RateLimitHeadersListener:
    """Writes the ``X-RateLimit-*`` headers of the limit that speaks for a response.

    The limit is the one a route's rate limit left on the request, when it
    exposes its state: the calls a route may still make, how many a full
    limit allows, and when it is full again, in seconds since the epoch. A
    response already carrying any of the three keeps its own. The response
    is made private too, so a shared cache never serves one caller's count
    to another.
    """

    __slots__ = ()

    def on_response(self, event: ResponseEvent) -> None:
        """Report the limit that speaks for the response, if one does."""
        applied = applied_rate_limit(event.request)
        if applied is None or applied.rate_limit.reset_at is None:
            return
        headers = event.headers
        if any(name in headers for name in (_LIMIT, _REMAINING, _RESET)):
            return

        headers[_LIMIT] = str(applied.rate_limit.limit // applied.tokens)
        headers[_REMAINING] = str(max(0, int(applied.remaining_calls)))
        headers[_RESET] = str(int(applied.rate_limit.reset_at.timestamp()))
        directives = [
            directive.strip()
            for directive in headers.get("cache-control", "").split(",")
            if directive.strip() and directive.strip().lower() != "public"
        ]
        if not any(directive.lower() in {"private", "no-store"} for directive in directives):
            directives.append("private")
        headers["cache-control"] = ", ".join(directives)
