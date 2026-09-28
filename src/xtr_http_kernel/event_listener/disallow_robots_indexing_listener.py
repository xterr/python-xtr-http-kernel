"""Keeping every response out of search indexes, when the application asks."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from xtr_http_kernel.event import ResponseEvent

__all__ = ["DisallowRobotsIndexingListener"]


@final
class DisallowRobotsIndexingListener:
    """Marks every outgoing response ``X-Robots-Tag: noindex`` when enabled.

    A staging deployment or an internal tool wants the whole application out
    of search indexes, not one page: a response header set in one listener
    beats a meta tag repeated in every template.
    """

    __slots__ = ("_enabled",)

    def __init__(self, enabled: bool) -> None:
        """Mark responses when ``enabled``; stay silent otherwise."""
        self._enabled = enabled

    def on_response(self, event: ResponseEvent) -> None:
        """Stamp the outgoing head, when marking is on."""
        if self._enabled:
            event.headers["X-Robots-Tag"] = "noindex"
