"""An uncaught exception written to the log with the request that caused it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from xtr_logging_contracts import EXCEPTION_KEY

if TYPE_CHECKING:
    from xtr_logging_contracts import LoggerInterface

    from xtr_http_kernel.event import ExceptionEvent

__all__ = ["ErrorLoggingListener"]

_SERVER_ERROR: Final = 500


@final
class ErrorLoggingListener:
    """Writes every exception the lifecycle announces to one logger.

    The level follows whose fault the failure is: an exception carrying an
    integer ``status_code`` below 500 is the caller's, and logged ``error``;
    a server status, or an exception saying nothing about status, is logged
    ``critical``. The exception itself travels under the logging contract's
    exception key, so formatters print its class, origin and cause.
    """

    __slots__ = ("_logger",)

    def __init__(self, logger: LoggerInterface) -> None:
        """Write to ``logger`` — the bundle hands in the request channel's."""
        self._logger = logger

    def on_exception(self, event: ExceptionEvent) -> None:
        """Log the failure, leaving the response to whoever answers it."""
        status = getattr(event.exception, "status_code", None)
        known = status if isinstance(status, int) else None
        write = (
            self._logger.error
            if known is not None and known < _SERVER_ERROR
            else self._logger.critical
        )
        write(
            "handling {method} {path} raised",
            {
                "method": event.request.method,
                "path": event.request.url.path,
                EXCEPTION_KEY: event.exception,
            },
        )
