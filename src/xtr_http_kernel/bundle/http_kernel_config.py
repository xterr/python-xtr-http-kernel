"""Configuration for :class:`~xtr_http_kernel.bundle.http_kernel_bundle.HttpKernelBundle`."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from xtr_http_kernel.exception.invalid_argument_error import InvalidArgumentError

__all__ = ["HttpKernelConfig"]

_HTTP_TOKEN: Final = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")
"""What a header field name may be made of."""


@dataclass(frozen=True, slots=True)
class HttpKernelConfig:
    """What an application may change about the request lifecycle.

    Attributes:
        request_id_header: The header the request id is read from and echoed
            on. Must be a non-empty HTTP token.
        trust_request_id: Whether a well-formed incoming id is kept. When
            false every request gets a fresh one.
        disallow_search_indexing: Whether every response is marked
            ``X-Robots-Tag: noindex``.
        log_channel: The logging channel the error listener writes to. The
            bundle declares the default channel on the logging config; an
            application choosing another name declares that channel in its
            own logging configuration.
        middleware_priority: Where the lifecycle middleware sits among the
            contributed factories — highest outermost.
        app: The ``"package.module:app"`` import string the console commands
            load the application from, when they need one.

    Raises:
        InvalidArgumentError: When ``request_id_header`` is not an HTTP token,
            ``log_channel`` is empty, or ``app`` does not hold exactly one
            module and one attribute around a single ``:``.
    """

    request_id_header: str = "X-Request-Id"
    trust_request_id: bool = True
    disallow_search_indexing: bool = False
    log_channel: str = "request"
    middleware_priority: int = 0
    app: str | None = None

    def __post_init__(self) -> None:
        """Refuse values the lifecycle would silently misread."""
        if not _HTTP_TOKEN.fullmatch(self.request_id_header):
            message = (
                f"request_id_header must be a non-empty HTTP token, not {self.request_id_header!r}"
            )
            raise InvalidArgumentError(message)
        if not self.log_channel:
            message = "log_channel must not be empty"
            raise InvalidArgumentError(message)
        if self.app is not None:
            module, separator, attribute = self.app.partition(":")
            if not (module and separator and attribute) or ":" in attribute:
                message = f'app must read "package.module:app", not {self.app!r}'
                raise InvalidArgumentError(message)
