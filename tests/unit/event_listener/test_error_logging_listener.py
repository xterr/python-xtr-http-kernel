"""Unit tests for :class:`xtr_http_kernel.event_listener.ErrorLoggingListener`."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

from typing_extensions import override
from xtr_logging_contracts import EXCEPTION_KEY, AbstractLogger, Level

from xtr_http_kernel.event import ExceptionEvent
from xtr_http_kernel.event_listener import ErrorLoggingListener

if TYPE_CHECKING:
    from starlette.requests import Request
    from xtr_logging_contracts import Context, LevelLike


class RecordingLogger(AbstractLogger):
    """A fake keeping every call, so a test reads levels and context back."""

    def __init__(self) -> None:
        self.entries: list[tuple[Level, str, Context | None]] = []

    @override
    def log(self, level: LevelLike, message: str, /, context: Context | None = None) -> None:
        self.entries.append((Level.parse(level), message, context))


@final
class TeapotError(RuntimeError):
    """An exception carrying the status it stands for."""

    status_code: ClassVar[int] = 418


@final
class MisstatedError(RuntimeError):
    """An exception whose status attribute is not a number."""

    status_code: ClassVar[str] = "teapot"


def test_an_exception_without_a_status_logs_critical(http_request: Request) -> None:
    logger = RecordingLogger()
    error = RuntimeError("boom")

    ErrorLoggingListener(logger).on_exception(ExceptionEvent(http_request, error))

    (entry,) = logger.entries
    level, _message, context = entry
    assert level is Level.CRITICAL
    assert context is not None
    assert context[EXCEPTION_KEY] is error


def test_a_server_error_status_logs_critical(http_request: Request) -> None:
    logger = RecordingLogger()

    @final
    class UpstreamError(RuntimeError):
        status_code: ClassVar[int] = 503

    ErrorLoggingListener(logger).on_exception(ExceptionEvent(http_request, UpstreamError("down")))

    assert logger.entries[0][0] is Level.CRITICAL


def test_a_client_error_status_logs_error(http_request: Request) -> None:
    logger = RecordingLogger()

    ErrorLoggingListener(logger).on_exception(ExceptionEvent(http_request, TeapotError("no")))

    assert logger.entries[0][0] is Level.ERROR


def test_a_status_that_is_not_a_number_counts_as_unknown(http_request: Request) -> None:
    logger = RecordingLogger()

    ErrorLoggingListener(logger).on_exception(ExceptionEvent(http_request, MisstatedError("odd")))

    assert logger.entries[0][0] is Level.CRITICAL


def test_the_record_names_the_request(http_request: Request) -> None:
    logger = RecordingLogger()

    ErrorLoggingListener(logger).on_exception(ExceptionEvent(http_request, RuntimeError("boom")))

    context = logger.entries[0][2]
    assert context is not None
    assert context["method"] == "GET"
    assert context["path"] == "/books/978-0141439518"
