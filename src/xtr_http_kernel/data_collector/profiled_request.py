"""What a data collector is handed: one request, the response it got, and how it went."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["ProfiledRequest"]


@dataclass(frozen=True, slots=True)
class ProfiledRequest:
    """One request being profiled, as every data collector sees it.

    The response is its head only — status and headers — because the body is
    streamed and has not been sent when collecting starts.

    Attributes:
        request: The request, as the message served to the application. Its
            body is read only if something read it already.
        status_code: The status the response started with.
        headers: The response's headers, as they are leaving.
        state: The request's state bag — the one the framework's own request
            wraps, and every lifecycle listener writes to.
        exception: What handling raised, when it raised.
    """

    request: ServerRequestInterface
    status_code: int
    headers: Mapping[str, str]
    state: Mapping[str, object]
    exception: BaseException | None = None
