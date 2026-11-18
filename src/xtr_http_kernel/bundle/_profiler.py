"""The profiler's services, registered when ``HttpKernelConfig.profiler.enabled``.

Every factory here is read by the container, so the types its parameters
name are imported at runtime.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

from xtr_dependency_injection import ServiceKey, bundle_active
from xtr_dependency_injection.integration import register_detached_variable
from xtr_event_dispatcher import (
    EventDispatcherInterface,  # noqa: TC002 — read at runtime by the container
)
from xtr_event_dispatcher.bundle import LISTENER_TAG
from xtr_service_contracts import (
    ContainerInterface,  # noqa: TC002 — read at runtime by the container
)
from xtr_stopwatch import Stopwatch

from xtr_http_kernel.data_collector.ajax_data_collector import AjaxDataCollector
from xtr_http_kernel.data_collector.config_data_collector import ConfigDataCollector
from xtr_http_kernel.data_collector.data_collector_tag import DATA_COLLECTOR_TAG
from xtr_http_kernel.data_collector.data_collector_templates import DataCollectorTemplates
from xtr_http_kernel.data_collector.event_data_collector import EventDataCollector
from xtr_http_kernel.data_collector.exception_data_collector import ExceptionDataCollector
from xtr_http_kernel.data_collector.memory_data_collector import MemoryDataCollector
from xtr_http_kernel.data_collector.request_data_collector import RequestDataCollector
from xtr_http_kernel.data_collector.router_data_collector import RouterDataCollector
from xtr_http_kernel.data_collector.time_data_collector import TimeDataCollector
from xtr_http_kernel.event import ExceptionEvent, RequestEvent, ResponseEvent, TerminateEvent
from xtr_http_kernel.event_listener.profiler_listener import ProfilerListener
from xtr_http_kernel.middleware_tag import MIDDLEWARE_TAG
from xtr_http_kernel.profiler.file_profiler_storage import FileProfilerStorage
from xtr_http_kernel.profiler.profiler import Profiler
from xtr_http_kernel.profiler.profiler_storage_interface import ProfilerStorageInterface

from .route_recording_middleware_factory import RouteRecordingMiddlewareFactory

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

    from xtr_http_kernel.data_collector.data_collector_interface import DataCollectorInterface

    from .http_kernel_config import HttpKernelConfig

__all__ = ["register"]

# The profiler decides first and stores last: its request half runs before every
# other listener, the unit of work included, so the whole request is in its
# section; its terminate half runs before the unit of work closes, so the
# request's log records are still there to read.
_REQUEST_PRIORITY: Final = 16384
_REQUEST_LATE_PRIORITY: Final = -16384
_RESPONSE_PRIORITY: Final = -1024
_TERMINATE_PRIORITY: Final = -4096

_TEMPLATES: Final = "@xtr_web_profiler/collector"
_CORE_COLLECTORS: Final = (
    ("request", 335),
    ("time", 330),
    ("memory", 325),
    ("ajax", 315),
    ("exception", 305),
    ("logger", 300),
    ("events", 290),
    ("router", 285),
    ("config", -255),
)


def register(
    config: HttpKernelConfig, services: ServiceConfigurator, builder: ContainerBuilder
) -> None:
    """Register the profiler, its storage, its listener and the core collectors."""
    profiler = config.profiler
    if not builder.has(Stopwatch):
        _ = services.set(_stopwatch)
    folder = profiler.storage_path or str(
        Path(str(builder.get_parameter("kernel.cache_dir"))) / "profiler"
    )
    _ = services.instance(FileProfilerStorage(folder, timedelta(seconds=profiler.lifetime_seconds)))
    services.alias(ProfilerStorageInterface, FileProfilerStorage)
    _ = services.set(_profiler).set_argument("keys", ()).set_argument("enabled", profiler.collect)
    _ = services.set(_templates).set_argument("entries", ())
    _ = (
        services.set(_profiler_listener(config))
        .add_tag(LISTENER_TAG, event=RequestEvent, method="on_request", priority=_REQUEST_PRIORITY)
        .add_tag(
            LISTENER_TAG,
            event=RequestEvent,
            method="on_request_late",
            priority=_REQUEST_LATE_PRIORITY,
        )
        .add_tag(LISTENER_TAG, event=ExceptionEvent, method="on_exception")
        .add_tag(
            LISTENER_TAG, event=ResponseEvent, method="on_response", priority=_RESPONSE_PRIORITY
        )
        .add_tag(
            LISTENER_TAG, event=TerminateEvent, method="on_terminate", priority=_TERMINATE_PRIORITY
        )
    )
    # Inside the lifecycle middleware, so the route is noted before the response event.
    _ = services.set(RouteRecordingMiddlewareFactory).add_tag(
        MIDDLEWARE_TAG, priority=config.middleware_priority - 1
    )
    _register_collectors(services, builder)


def _register_collectors(services: ServiceConfigurator, builder: ContainerBuilder) -> None:
    factories: dict[str, Callable[..., object] | type] = {
        "request": RequestDataCollector,
        "time": _time_collector,
        "memory": MemoryDataCollector,
        "ajax": AjaxDataCollector,
        "exception": ExceptionDataCollector,
        "events": _event_collector,
        "router": RouterDataCollector,
    }
    if bundle_active(builder, "logging") and bool(builder.get_parameter("kernel.debug")):
        # Needs xtr-logging, which the logging bundle being active proves installed;
        # the handler it reads is there in debug mode only.
        from ._profiler_logging import logger_collector  # noqa: PLC0415 — xtr-logging is optional

        factories["logger"] = logger_collector
    for name, priority in _CORE_COLLECTORS:
        tag = {"name": name, "template": f"{_TEMPLATES}/{name}.html.j2", "priority": priority}
        if name == "config":
            _ = services.instance(
                ConfigDataCollector(
                    str(builder.get_parameter("kernel.environment")),
                    bool(builder.get_parameter("kernel.debug")),
                    cast("Mapping[str, str]", builder.get_parameter("kernel.bundles")),
                )
            ).add_tag(DATA_COLLECTOR_TAG, **tag)
        elif name in factories:
            _ = services.set(factories[name]).add_tag(DATA_COLLECTOR_TAG, **tag)


def _stopwatch() -> Stopwatch:
    """Build the stopwatch on its own monotonic clock, never the application's.

    Every new connection starts with nothing timed.
    """
    stopwatch = Stopwatch()
    register_detached_variable(*stopwatch.detached_variable)
    return stopwatch


async def _profiler(
    container: ContainerInterface,
    storage: ProfilerStorageInterface,
    keys: tuple[ServiceKey, ...],
    enabled: bool,
) -> Profiler:
    """Build the profiler over the collectors ``keys`` name, in the pass's order."""
    collectors = [
        cast("DataCollectorInterface", await container.get(provided, qualifier))
        for provided, qualifier in keys
    ]
    profiler = Profiler(storage, collectors, enabled=enabled)
    # A new connection starts undecided, whatever a request it was copied from decided.
    register_detached_variable(*profiler.detached_variable)
    return profiler


def _templates(entries: tuple[tuple[str, str], ...]) -> DataCollectorTemplates:
    """Hold the panels' templates, in the pass's order."""
    return DataCollectorTemplates(entries)


def _profiler_listener(
    config: HttpKernelConfig,
) -> Callable[[Profiler, Stopwatch], ProfilerListener]:
    """Build the factory giving the listener the profiler settings of ``config``."""
    settings = config.profiler

    def profiler_listener(profiler: Profiler, stopwatch: Stopwatch) -> ProfilerListener:
        return ProfilerListener(
            profiler,
            stopwatch,
            collect_parameter=settings.collect_parameter,
            only_exceptions=settings.only_exceptions,
            excluded_paths=settings.excluded_paths,
            excluded_status_codes=settings.excluded_status_codes,
        )

    return profiler_listener


def _time_collector(stopwatch: Stopwatch) -> TimeDataCollector:
    return TimeDataCollector(stopwatch)


def _event_collector(dispatcher: EventDispatcherInterface) -> EventDataCollector:
    return EventDataCollector(dispatcher)
