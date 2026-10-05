"""Logging for the direct variant: a fingers-crossed handler over the collector.

Everything buffers per unit of work; a record at ``warning`` or above
releases the whole buffer to the collecting handler as one batch, and a
quiet unit forwards nothing below the passthru floor.
"""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_logging import LoggingConfig
from xtr_logging.config import (
    ContextVarsProcessorConfig,
    FingersCrossedHandlerConfig,
    ServiceHandlerConfig,
    ServiceProcessorConfig,
)


@configure
def logging_config() -> LoggingConfig:
    return LoggingConfig(
        handlers={
            "hold": FingersCrossedHandlerConfig(
                action_level="warning",
                handler="collect",
                passthru_level="warning",
            ),
            "collect": ServiceHandlerConfig(id="collect"),
        },
        processors=(ServiceProcessorConfig(id="uid"), ContextVarsProcessorConfig()),
    )
