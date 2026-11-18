"""Profiles every request it is allowed to, as its response starts, and stores it once sent."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final, cast, final

from xtr_clock import SystemClock

from xtr_http_kernel.data_collector.profiled_request import ProfiledRequest
from xtr_http_kernel.profiler import _state_keys as keys
from xtr_http_kernel.profiler.profiler import DEBUG_TOKEN_HEADER

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableMapping, Sequence

    from xtr_clock import ClockInterface
    from xtr_stopwatch import Stopwatch, StopwatchEvent

    from xtr_http_kernel.event import ExceptionEvent, RequestEvent, ResponseEvent, TerminateEvent
    from xtr_http_kernel.profiler.profile import Profile
    from xtr_http_kernel.profiler.profiler import Profiler

__all__ = ["ProfilerListener"]

_TRUE: Final = frozenset({"1", "true", "on", "yes"})
_FALSE: Final = frozenset({"0", "false", "off", "no", ""})
_CONTROLLER: Final = "controller"
_SECTION: Final = "section"
_SERVER_ERROR: Final = 500
_UNPROFILED_SECTION: Final = "unprofiled"


@final
class ProfilerListener:
    """Decides whether each request is profiled, collects it, and stores the profile.

    - At the request, first of all: the request starts from the configured
      default; a path matching ``excluded_paths`` is turned off, and
      ``collect_parameter`` — a query parameter, or a state entry — turns it
      on or off. The stopwatch opens the request's section. Last of all, the
      ``controller`` event starts: what follows is the application's own work.
    - At an uncaught exception: it is noted for the profile.
    - At the response, late: the ``controller`` event stops, every collector
      runs, and the response carries ``X-Debug-Token``.
    - Once everything has been sent: the section closes and the profile is
      completed and stored. A request whose response never started — handling
      raised and nothing answered — is profiled here instead, as a 500, so
      the failure can still be read.
    """

    __slots__ = (
        "_clock",
        "_collect_parameter",
        "_excluded_paths",
        "_excluded_status_codes",
        "_only_exceptions",
        "_profiler",
        "_stopwatch",
    )

    def __init__(  # noqa: PLR0913 — the listener takes each setting it reads by name
        self,
        profiler: Profiler,
        stopwatch: Stopwatch,
        *,
        collect_parameter: str | None = None,
        only_exceptions: bool = False,
        excluded_paths: Sequence[str] = (),
        excluded_status_codes: Sequence[int] = (),
        clock: ClockInterface | None = None,
    ) -> None:
        """Profile through ``profiler``, timing each request's section on ``stopwatch``.

        Args:
            profiler: What collects and stores the profiles.
            stopwatch: Where each request's section is timed.
            collect_parameter: The query parameter or state key that turns
                profiling on or off for one request.
            only_exceptions: Profile only requests whose handling raised.
            excluded_paths: Regular expressions; a matching path is not profiled.
            excluded_status_codes: Statuses a profile is not kept for.
            clock: What a request's arrival is read from;
                :class:`~xtr_clock.SystemClock` by default.
        """
        self._profiler = profiler
        self._stopwatch = stopwatch
        self._collect_parameter = collect_parameter
        self._only_exceptions = only_exceptions
        self._excluded_paths = (
            re.compile("|".join(f"(?:{pattern})" for pattern in excluded_paths))
            if excluded_paths
            else None
        )
        self._excluded_status_codes = frozenset(excluded_status_codes)
        self._clock: ClockInterface = clock if clock is not None else SystemClock()

    def on_request(self, event: RequestEvent) -> None:
        """Settle whether the request is profiled, and open its section."""
        self._profiler.begin_request()
        event.state[keys.START] = self._clock.now().timestamp()
        path = event.request.get_uri().get_path()
        if self._excluded_paths is not None and self._excluded_paths.search(path):
            self._profiler.disable()
        else:
            asked = self._asked(event.request.get_query_params(), event.state)
            if asked is True:
                self._profiler.enable()
            elif asked is False:
                self._profiler.disable()
        self._profiler.begin_tracing()
        self._stopwatch.reset()
        self._stopwatch.open_section()

    def on_request_late(self, event: RequestEvent) -> None:
        """Start timing the application's own handling, once every request listener ran."""
        event.state[keys.CONTROLLER] = self._stopwatch.start(_CONTROLLER, _SECTION)

    def on_exception(self, event: ExceptionEvent) -> None:
        """Note what handling raised."""
        event.state[keys.EXCEPTION] = event.exception

    def on_response(self, event: ResponseEvent) -> None:
        """Collect the profile and name it on the response."""
        _stop_controller(event.state)
        profiled = ProfiledRequest(
            event.request,
            event.status_code,
            event.headers,
            event.state,
            _exception(event.state),
        )
        profile = self._collect(profiled, event.state)
        if profile is not None:
            event.headers[DEBUG_TOKEN_HEADER] = profile.token

    async def on_terminate(self, event: TerminateEvent) -> None:
        """Close the section, then complete and store the profile."""
        if keys.START not in event.state:
            # A listener answered before this one's request half ran: nothing was opened.
            return
        _stop_controller(event.state)
        exception = _exception(event.state)
        if keys.PROFILE not in event.state and exception is not None:
            # The response never started, so nothing collected at it: profile the
            # failure as the 500 the server answered with.
            _ = self._collect(
                ProfiledRequest(event.request, _SERVER_ERROR, {}, event.state, exception),
                event.state,
            )
        kept = cast("tuple[Profile, ProfiledRequest] | None", event.state.get(keys.PROFILE))
        self._stopwatch.stop_section(kept[0].token if kept is not None else _UNPROFILED_SECTION)
        if kept is not None:
            profile, profiled = kept
            _ = await self._profiler.save_profile(profile, profiled)

    def _collect(
        self, profiled: ProfiledRequest, state: MutableMapping[str, object]
    ) -> Profile | None:
        if self._only_exceptions and profiled.exception is None:
            return None
        if profiled.status_code in self._excluded_status_codes:
            return None
        profile = self._profiler.collect(profiled)
        if profile is not None:
            state[keys.TOKEN] = profile.token
            state[keys.PROFILE] = (profile, profiled)
        return profile

    def _asked(self, query: Mapping[str, object], state: Mapping[str, object]) -> bool | None:
        """Return what ``collect_parameter`` asks for, or ``None`` when it is absent or unclear."""
        if self._collect_parameter is None:
            return None
        value = query.get(self._collect_parameter, state.get(self._collect_parameter))
        if isinstance(value, bool):
            return value
        if not isinstance(value, str):
            return None
        text = value.strip().lower()
        if text in _TRUE:
            return True
        return False if text in _FALSE else None


def _exception(state: Mapping[str, object]) -> BaseException | None:
    exception = state.get(keys.EXCEPTION)
    return exception if isinstance(exception, BaseException) else None


def _stop_controller(state: Mapping[str, object]) -> None:
    controller = cast("StopwatchEvent | None", state.get(keys.CONTROLLER))
    if controller is not None and controller.is_started():
        _ = controller.stop()
