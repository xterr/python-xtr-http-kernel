"""Logging for the queued variant: a queue handler in front of the fingers-crossed one.

Records cross to a worker thread with their logging context captured, so
the fingers-crossed handler behind the queue still buffers per unit of
work. Closing the factory at kernel shutdown drains the queue, so a test
asserting after the application life ended never waits on a sleep.
"""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_logging import LoggingConfig
from xtr_logging.config import (
    ContextVarsProcessorSpec,
    FingersCrossedHandlerSpec,
    QueueHandlerSpec,
    ServiceHandlerSpec,
    ServiceProcessorSpec,
)


@configure
def logging_config() -> LoggingConfig:
    return LoggingConfig(
        handlers={
            "gate": QueueHandlerSpec(handler="hold"),
            "hold": FingersCrossedHandlerSpec(
                action_level="warning",
                handler="collect",
                passthru_level="warning",
            ),
            "collect": ServiceHandlerSpec(id="collect"),
        },
        processors=(ServiceProcessorSpec(id="uid"), ContextVarsProcessorSpec()),
    )
