"""Logging for the profiled application: the defaults, and nothing written anywhere."""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_logging import LoggingConfig
from xtr_logging.config import NullHandlerConfig


@configure
def logging_config() -> LoggingConfig:
    return LoggingConfig(handlers={"silent": NullHandlerConfig()})
