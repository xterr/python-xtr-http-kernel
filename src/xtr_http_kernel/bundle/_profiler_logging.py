"""The profiler's side of logging: a handler keeping each request's records, and its collector.

Imported only once the logging bundle is active, which proves xtr-logging
installed: the container reads the ``DebugHandler`` annotations at runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast

from xtr_logging import DebugHandler, HandlerInterface
from xtr_logging.config import LoggingConfig, ServiceHandlerConfig

from xtr_http_kernel.data_collector.logger_data_collector import LoggerDataCollector

if TYPE_CHECKING:
    from xtr_dependency_injection import ServiceConfigurator

__all__ = ["DEBUG_HANDLER", "add_debug_handler", "logger_collector", "register_debug_handler"]

DEBUG_HANDLER: Final = "profiler"
"""The logging handler, and its service's qualifier, keeping each request's records."""

# Consulted before every other handler, so one that stops records bubbling
# never keeps them from the profile.
_FIRST: Final = 1_000_000


def add_debug_handler(config: object) -> object:
    """Add the debug handler to the logging configuration, on every channel, first."""
    return cast("LoggingConfig", config).with_handler(
        DEBUG_HANDLER, ServiceHandlerConfig(id=DEBUG_HANDLER, priority=_FIRST)
    )


def register_debug_handler(services: ServiceConfigurator) -> None:
    """Register the debug handler as the handler service the logging configuration names."""
    _ = services.set(debug_handler)
    services.alias(HandlerInterface, DebugHandler, alias_qualifier=DEBUG_HANDLER)


def debug_handler() -> DebugHandler:
    """Build the handler keeping the records of each request."""
    return DebugHandler()


def logger_collector(handler: DebugHandler) -> LoggerDataCollector:
    """Build the collector reading ``handler``."""
    return LoggerDataCollector(handler)
