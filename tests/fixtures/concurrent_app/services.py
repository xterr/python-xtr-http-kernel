"""Services and journals the concurrency tests observe a kernel through.

The collecting handler keeps batch boundaries: what a fingers-crossed
release forwarded together arrives as one tuple, and a record passed
straight through arrives alone. The uid processor is registered as a
service so an endpoint can read the id the open unit of work carries.
Module-level journals let a test reach the instances its application life
created, newest last.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_dependency_injection import as_service, configure
from xtr_event_dispatcher.bundle import EventDispatcherConfig
from xtr_logging import HandlerInterface, ProcessorInterface, UidProcessor

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_logging import LogRecord


@final
class CollectingHandler:
    """Keeps everything it received, with batch boundaries preserved."""

    def __init__(self) -> None:
        self.batches: list[tuple[LogRecord, ...]] = []
        self.singles: list[LogRecord] = []

    def is_handling(self, record: LogRecord, /) -> bool:
        del record
        return True

    def handle(self, record: LogRecord, /) -> bool:
        self.singles.append(record)
        return False

    def handle_batch(self, records: Sequence[LogRecord], /) -> None:
        self.batches.append(tuple(records))

    def close(self) -> None:
        """Nothing to release: the journals belong to the test."""


COLLECTED: list[CollectingHandler] = []
"""Every collecting handler built, newest last."""

UID_PROCESSORS: list[UidProcessor] = []
"""Every uid processor built, newest last."""


@configure
def event_dispatcher_config() -> EventDispatcherConfig:
    # Tracing ON: a per-unit trace only exists then, and the lifecycle
    # middleware frames each request as one unit of the traced dispatcher.
    return EventDispatcherConfig(trace=True)


@as_service(qualifier="collect")
def collect_handler() -> HandlerInterface:
    handler = CollectingHandler()
    COLLECTED.append(handler)
    return handler


@as_service(qualifier="uid")
def uid_processor() -> ProcessorInterface:
    processor = UidProcessor(length=16)
    UID_PROCESSORS.append(processor)
    return processor
