"""The xtr-http-kernel bundle: the request lifecycle, under the container.

The bundle is the integration, never the library: an application drives the
lifecycle itself with :func:`xtr_http_kernel.setup`, and lists this bundle so
the container owns the pieces the lifecycle reaches for — the middleware
factory the setup call composes, and the listeners that give every request
an id, a log record on failure and a unit of work of its own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast, final

from typing_extensions import override

# ServiceKey stays a runtime import: it annotates a factory parameter the
# container evaluates when the definitions are emitted.
from xtr_dependency_injection import (
    Bundle,
    ServiceKey,
    as_bundle,
    bundle_active,
    required_bundle,
)
from xtr_event_dispatcher.bundle import EventDispatcherBundle

# Read at runtime: the container fills factory parameters from annotations.
from xtr_logging_contracts import LoggerInterface
from xtr_service_contracts import ContainerInterface  # noqa: TC002

from xtr_http_kernel.event import ExceptionEvent, RequestEvent, ResponseEvent, TerminateEvent
from xtr_http_kernel.event_listener import (
    DisallowRobotsIndexingListener,
    ErrorLoggingListener,
    RequestIdListener,
)
from xtr_http_kernel.exception import InvalidMiddlewarePriorityError
from xtr_http_kernel.middleware_stack import MiddlewareStack
from xtr_http_kernel.middleware_tag import MIDDLEWARE_TAG

from .http_kernel_config import HttpKernelConfig
from .request_lifecycle_middleware_factory import RequestLifecycleMiddlewareFactory

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

    from xtr_http_kernel.middleware_stack import MiddlewareFactory

__all__ = ["HttpKernelBundle"]

_LISTENER_TAG: Final = "event_dispatcher.listener"
"""The tag the event dispatcher bundle reads listeners from."""

# The unit of work opens before anything else contributes and closes after
# everything else has heard the terminate; the request id settles right after
# the unit opens, so every record made while handling carries it.
_UNIT_OPEN_PRIORITY: Final = 8192
_REQUEST_ID_PRIORITY: Final = 4096
_UNIT_CLOSE_PRIORITY: Final = -8192


@final
@required_bundle(EventDispatcherBundle)
@required_bundle("xtr_logging.bundle:LoggingBundle", ignore_on_invalid=True)
@required_bundle("xtr_console.bundle:ConsoleBundle", ignore_on_invalid=True)
@as_bundle("http_kernel", config=HttpKernelConfig)
class HttpKernelBundle(Bundle[HttpKernelConfig]):
    """Puts the request lifecycle's services under the container."""

    @override
    def prepend_extension(self, builder: ContainerBuilder) -> None:
        """When ``logging`` is active, declare the default request channel on its config.

        The channel name here is the config default: this bundle's own config
        resolves after logging's, so a renamed channel is declared by the
        application in its logging configuration instead.
        """
        if bundle_active(builder, "logging"):
            builder.prepend_extension_config("logging", _add_request_channel)

    @override
    def load_extension(
        self,
        config: HttpKernelConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register the middleware factory and the listeners from ``config``.

        The listeners that write to a log join only when the logging bundle
        is active. The console commands and their module arrive with the
        router commands; until then a console-only application simply gets
        no commands from this bundle.
        """
        _ = services.set(RequestLifecycleMiddlewareFactory).add_tag(
            MIDDLEWARE_TAG, priority=config.middleware_priority
        )
        _ = services.set(_middleware_stack).set_argument("keys", ())
        _ = (
            services.set(RequestIdListener)
            .set_argument("header", config.request_id_header)
            .set_argument("trust_incoming", config.trust_request_id)
            .add_tag(
                _LISTENER_TAG,
                event=RequestEvent,
                method="on_request",
                priority=_REQUEST_ID_PRIORITY,
            )
            .add_tag(_LISTENER_TAG, event=ResponseEvent, method="on_response")
        )
        _ = (
            services.set(DisallowRobotsIndexingListener)
            .set_argument("enabled", config.disallow_search_indexing)
            .add_tag(_LISTENER_TAG, event=ResponseEvent, method="on_response")
        )
        if bundle_active(builder, "logging"):
            # Needs the optional logging extra, which being here proves installed.
            from xtr_http_kernel.event_listener.log_unit_listener import (  # noqa: PLC0415
                LogUnitListener,
            )

            _ = (
                services.set(LogUnitListener)
                .add_tag(
                    _LISTENER_TAG,
                    event=RequestEvent,
                    method="on_request",
                    priority=_UNIT_OPEN_PRIORITY,
                )
                .add_tag(
                    _LISTENER_TAG,
                    event=TerminateEvent,
                    method="on_terminate",
                    priority=_UNIT_CLOSE_PRIORITY,
                )
            )
            _ = services.set(_error_logging_listener(config.log_channel)).add_tag(
                _LISTENER_TAG, event=ExceptionEvent, method="on_exception"
            )

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Order every tagged middleware into the stack, highest priority outermost.

        Runs after every bundle loaded, so the builder holds every tag. The
        tag's ``priority`` attribute is 0 when absent; ties keep
        registration order.

        Raises:
            InvalidMiddlewarePriorityError: If a tag's ``priority`` is not
                an integer.
        """
        entries: list[tuple[int, int, ServiceKey]] = []
        for order, (key, attributes) in enumerate(
            builder.find_tagged_service_ids(MIDDLEWARE_TAG).items()
        ):
            priority = attributes[0].get("priority", 0)
            if not isinstance(priority, int):
                raise InvalidMiddlewarePriorityError(key, priority)
            entries.append((priority, order, key))
        entries.sort(key=lambda entry: (-entry[0], entry[1]))
        _ = builder.get_definition(MiddlewareStack).set_argument(
            "keys", tuple(key for _, _, key in entries)
        )


async def _middleware_stack(
    container: ContainerInterface, keys: tuple[ServiceKey, ...]
) -> MiddlewareStack:
    """Build the stack by resolving each ordered key through ``container``.

    ``keys`` comes from the bundle's ``process`` hook: the tagged
    definitions, already ordered highest priority first.
    """
    factories = [
        cast("MiddlewareFactory", await container.get(provided, qualifier))
        for provided, qualifier in keys
    ]
    return MiddlewareStack(factories)


def _error_logging_listener(
    channel: str,
) -> Callable[[ContainerInterface], Coroutine[object, object, ErrorLoggingListener]]:
    """Build the factory giving the error listener the ``channel`` logger.

    The channel comes from this bundle's config, so it cannot sit in an
    annotation the way a constant channel could: the factory asks the
    container at build time instead.
    """

    async def error_logging_listener(container: ContainerInterface) -> ErrorLoggingListener:
        return ErrorLoggingListener(await container.get(LoggerInterface, channel))

    return error_logging_listener


def _add_request_channel(config: object) -> object:
    """Declare the default channel through the logging config's own ``with_channels``.

    Duck-typed: this bundle depends on the logging contracts only, never on
    xtr-logging, so it asks the config it is handed rather than importing
    its type.
    """
    with_channels = cast("Callable[[str], object] | None", getattr(config, "with_channels", None))
    default_channel = HttpKernelConfig().log_channel
    return with_channels(default_channel) if with_channels is not None else config
