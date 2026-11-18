"""Configuration of the request profiler, under :class:`HttpKernelConfig`."""

from __future__ import annotations

import re
from dataclasses import dataclass

from xtr_http_kernel.exception.invalid_argument_error import InvalidArgumentError

__all__ = ["ProfilerConfig"]


@dataclass(frozen=True, slots=True)
class ProfilerConfig:
    """What an application may change about profiling its requests.

    Off by default: a profile holds every request's headers, cookies and
    state, so it is turned on only where a developer reads it — the web
    profiler's bundle turns it on in the environments it is listed for.

    Attributes:
        enabled: Whether requests are profiled at all.
        collect: Whether a request is profiled unless it asks otherwise; off,
            only a request carrying ``collect_parameter`` is.
        collect_parameter: A query parameter, or a state bag key, whose
            boolean value turns profiling on or off for that request alone.
        only_exceptions: Profile only the requests whose handling raised.
        excluded_paths: Regular expressions; a request whose path matches one
            is not profiled. The profiler's own pages are excluded by default.
        excluded_status_codes: Statuses a profile is not kept for.
        storage_path: Where profiles are kept; ``None`` keeps them under the
            kernel's cache directory, in ``profiler/``.
        lifetime_seconds: How long a profile is kept.

    Raises:
        InvalidArgumentError: When an ``excluded_paths`` entry is not a
            regular expression, ``collect_parameter`` is empty, or
            ``lifetime_seconds`` is below one.
    """

    enabled: bool = False
    collect: bool = True
    collect_parameter: str | None = None
    only_exceptions: bool = False
    excluded_paths: tuple[str, ...] = ("^/_(wdt|profiler)",)
    excluded_status_codes: tuple[int, ...] = ()
    storage_path: str | None = None
    lifetime_seconds: int = 172_800

    def __post_init__(self) -> None:
        """Refuse values profiling would misread."""
        for pattern in self.excluded_paths:
            try:
                _ = re.compile(pattern)
            except re.error as error:
                message = f"excluded_paths holds {pattern!r}, which is not a regular expression"
                raise InvalidArgumentError(message) from error
        if self.collect_parameter == "":
            message = "collect_parameter must not be empty; leave it None to read no parameter"
            raise InvalidArgumentError(message)
        if self.lifetime_seconds < 1:
            message = f"lifetime_seconds must be at least 1, not {self.lifetime_seconds}"
            raise InvalidArgumentError(message)
