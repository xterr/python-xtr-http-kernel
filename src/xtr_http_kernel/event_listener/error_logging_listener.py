"""An uncaught exception written to the log with the request that caused it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from xtr_logging_contracts import EXCEPTION_KEY

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_logging_contracts import Context, LoggerInterface

    from xtr_http_kernel.event import ExceptionEvent

    _Write = Callable[[str, Context], None]

__all__ = ["ErrorLoggingListener"]

_SERVER_ERROR: Final = 500


@final
class ErrorLoggingListener:
    """Writes every exception the lifecycle announces to one logger.

    The level follows whose fault the failure is. A cancellation, an
    interrupt or an exit is nobody's — it is how a timeout, a disconnected
    caller or a shutdown reaches the lifecycle — so it is logged ``info``.
    Of the failures that are left, one carrying an integer ``status_code``
    below 500 is the caller's, and logged ``error``; a server status, or an
    exception saying nothing about status, is logged ``critical``. The
    exception itself travels under the logging contract's exception key, so
    formatters print its class, origin and cause.
    """

    __slots__ = ("_logger",)

    def __init__(self, logger: LoggerInterface) -> None:
        """Write to ``logger`` — the bundle hands in the request channel's."""
        self._logger = logger

    def on_exception(self, event: ExceptionEvent) -> None:
        """Log the failure, leaving the response to whoever answers it."""
        self._write_for(event.exception)(
            "handling {method} {path} raised",
            {
                "method": event.request.method,
                "path": event.request.url.path,
                EXCEPTION_KEY: event.exception,
            },
        )

    def _write_for(self, exception: BaseException) -> _Write:
        """Return the logger method ``exception`` deserves."""
        if not isinstance(exception, Exception):
            return self._logger.info
        status = getattr(exception, "status_code", None)
        known = status if isinstance(status, int) else None
        if known is not None and known < _SERVER_ERROR:
            return self._logger.error
        return self._logger.critical
