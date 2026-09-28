"""Logging for the fixture application: every record lands in a test handler.

The handler factory journals each handler it builds, so a test reaches the
one its application life created and reads the records back.
"""

from __future__ import annotations

from xtr_dependency_injection import as_service, configure
from xtr_logging import HandlerInterface, LoggingConfig, TestHandler
from xtr_logging.config import ContextVarsProcessorSpec, ServiceHandlerSpec

CAPTURED: list[TestHandler] = []
"""Every capture handler built, newest last."""


@configure
def logging_config() -> LoggingConfig:
    return LoggingConfig(
        handlers={"capture": ServiceHandlerSpec(id="capture")},
        processors=(ContextVarsProcessorSpec(),),
    )


@as_service(qualifier="capture")
def capture_handler() -> HandlerInterface:
    handler = TestHandler()
    CAPTURED.append(handler)
    return handler
