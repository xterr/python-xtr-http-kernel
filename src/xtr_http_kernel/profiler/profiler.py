"""Turns a request into a profile, stores it, and finds it again."""

from __future__ import annotations

import secrets
from contextvars import ContextVar
from functools import partial
from typing import TYPE_CHECKING, Final, cast, final, override

from starlette.concurrency import run_in_threadpool
from xtr_clock import SystemClock

from xtr_http_kernel.data_collector.late_data_collector_interface import (
    LateDataCollectorInterface,
)
from xtr_http_kernel.data_collector.tracing_data_collector_interface import (
    TracingDataCollectorInterface,
)

from .profile import Profile

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from xtr_clock import ClockInterface

    from xtr_http_kernel.data_collector.data_collector_interface import DataCollectorInterface
    from xtr_http_kernel.data_collector.profiled_request import ProfiledRequest

    from .profile_summary import ProfileSummary
    from .profiler_storage_interface import ProfilerStorageInterface

__all__ = ["DEBUG_TOKEN_HEADER", "Profiler"]

DEBUG_TOKEN_HEADER: Final = "X-Debug-Token"  # noqa: S105 — a header name, not a secret
"""The response header naming the profile a response was stored under."""

_TOKEN_BYTES: Final = 3
_UNKNOWN_IP: Final = "Unknown"


@final
class _Switch:
    """Whether the current request is profiled, changed in place wherever it is read."""

    __slots__ = ("enabled",)

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled


@final
class Profiler:
    """Runs every collector over a request and stores what they kept as one profile.

    ```python
    profile = profiler.collect(profiled)  # as the response starts
    await profiler.save_profile(profile, profiled)  # once it has left
    await profiler.load_profile(profile.token)
    ```

    Whether a request is profiled is decided per request: :meth:`begin_request`
    starts it from the configured default, and :meth:`enable` or
    :meth:`disable` — from a listener, a route, a page of the profiler itself
    — change it for that request alone, however many others are being served
    at the same time.
    """

    __slots__ = ("_clock", "_collectors", "_enabled", "_storage", "_switch", "detached_variable")

    def __init__(
        self,
        storage: ProfilerStorageInterface,
        collectors: Sequence[DataCollectorInterface] = (),
        clock: ClockInterface | None = None,
        enabled: bool = True,
    ) -> None:
        """Profile with ``collectors``, in order, into ``storage``.

        Args:
            storage: Where profiles are written and read back.
            collectors: Every collector, in the order their panels are shown.
            clock: What a profile's time is read from;
                :class:`~xtr_clock.SystemClock` by default.
            enabled: Whether a request is profiled unless told otherwise.
        """
        self._storage = storage
        self._collectors: dict[str, DataCollectorInterface] = {
            collector.name: collector for collector in collectors
        }
        self._clock: ClockInterface = clock if clock is not None else SystemClock()
        self._enabled = enabled
        self._switch: ContextVar[_Switch | None] = ContextVar("profiler_switch", default=None)
        self.detached_variable: tuple[ContextVar[_Switch | None], None] = (self._switch, None)
        """The variable a new connection must start without, and the value it starts from."""

    def begin_request(self) -> None:
        """Start the calling context's request from the configured default."""
        _ = self._switch.set(_Switch(self._enabled))

    def begin_tracing(self) -> None:
        """Start every tracing collector recording the calling context's request, when profiled.

        Called once whether the request is profiled has been decided; an
        unprofiled request starts nothing, so its instrumentation records nothing.
        """
        if not self.is_enabled():
            return
        for collector in self._collectors.values():
            if isinstance(collector, TracingDataCollectorInterface):
                collector.begin_request()

    def is_enabled(self) -> bool:
        """Tell whether the current request is profiled."""
        switch = self._switch.get()
        return switch.enabled if switch is not None else self._enabled

    def enable(self) -> None:
        """Profile the current request."""
        self._current().enabled = True

    def disable(self) -> None:
        """Leave the current request unprofiled."""
        self._current().enabled = False

    def has(self, name: str) -> bool:
        """Tell whether a collector named ``name`` is registered."""
        return name in self._collectors

    def get(self, name: str) -> DataCollectorInterface | None:
        """Return the collector named ``name``, or ``None``."""
        return self._collectors.get(name)

    def all(self) -> tuple[DataCollectorInterface, ...]:
        """Return every collector, in panel order."""
        return tuple(self._collectors.values())

    def collect(self, profiled: ProfiledRequest) -> Profile | None:
        """Return a profile of ``profiled`` holding every collector's data; ``None`` when off."""
        if not self.is_enabled():
            return None
        request = profiled.request
        profile = Profile(
            secrets.token_hex(_TOKEN_BYTES),
            ip=_client_ip(request.get_server_params()),
            method=request.get_method(),
            url=str(request.get_uri()),
            time=int(self._clock.now().timestamp()),
            status_code=profiled.status_code,
            has_errors=profiled.exception is not None,
        )
        for name, collector in self._collectors.items():
            profile.add_collector(name, collector.collect(profiled))
        return profile

    async def save_profile(self, profile: Profile, profiled: ProfiledRequest) -> bool:
        """Complete ``profile`` with what settled late, then store it in a worker thread."""
        for name, collector in self._collectors.items():
            if isinstance(collector, LateDataCollectorInterface) and profile.has_collector(name):
                data = dict(profile.get_collector(name))
                profile.add_collector(name, collector.late_collect(data, profiled))
        profile.has_errors = profile.has_errors or _logged_errors(profile)
        return await run_in_threadpool(self._storage.write, profile)

    async def load_profile(self, token: str) -> Profile | None:
        """Return the profile stored under ``token``, or ``None``.

        Raises:
            InvalidTokenError: When ``token`` is not a valid token.
        """
        return await run_in_threadpool(self._storage.read, token)

    async def load_profile_from_response(self, headers: Mapping[str, str]) -> Profile | None:
        """Return the profile the response carrying ``headers`` was stored under, or ``None``."""
        wanted = DEBUG_TOKEN_HEADER.lower()
        token = next((value for name, value in headers.items() if name.lower() == wanted), None)
        return await self.load_profile(token) if token else None

    async def find(  # noqa: PLR0913 — every search filter is its own keyword
        self,
        ip: str | None,
        url: str | None,
        limit: int,
        method: str | None,
        *,
        start: int | None = None,
        end: int | None = None,
        status_code: int | None = None,
        filter: Callable[[ProfileSummary], bool] | None = None,  # noqa: A002 — the filter is what it is
    ) -> list[ProfileSummary]:
        """Return up to ``limit`` stored profiles, newest first, matching every filter given."""
        search = partial(
            self._storage.find,
            ip,
            url,
            limit,
            method,
            start=start,
            end=end,
            status_code=status_code,
            filter=filter,
        )
        return await run_in_threadpool(search)

    async def purge(self) -> None:
        """Remove every stored profile."""
        await run_in_threadpool(self._storage.purge)

    def _current(self) -> _Switch:
        switch = self._switch.get()
        if switch is None:
            switch = _Switch(self._enabled)
            _ = self._switch.set(switch)
        return switch

    @override
    def __repr__(self) -> str:
        """Return the collectors, by name."""
        return f"{type(self).__name__}(collectors={list(self._collectors)!r})"


def _client_ip(server_params: Mapping[str, object]) -> str:
    client = server_params.get("client")
    if isinstance(client, tuple | list) and client:
        host = cast("object", client[0])
        return str(host)
    return _UNKNOWN_IP


def _logged_errors(profile: Profile) -> bool:
    if not profile.has_collector("logger"):
        return False
    count = profile.get_collector("logger").get("error_count")
    return isinstance(count, int) and count > 0
