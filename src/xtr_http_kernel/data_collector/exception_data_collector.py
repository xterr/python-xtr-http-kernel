"""What handling raised, with every frame it passed through."""

from __future__ import annotations

import linecache
import traceback
from typing import TYPE_CHECKING, Final, cast, final

from .clone_var import clone_var

if TYPE_CHECKING:
    from types import TracebackType

    from .profiled_request import ProfiledRequest

__all__ = ["ExceptionDataCollector"]

_NAME: Final = "exception"
_CONTEXT_LINES: Final = 5
_MAX_FRAMES: Final = 50
_MAX_CHAIN: Final = 5


@final
class ExceptionDataCollector:
    """Keeps the exception handling raised: its class, message, chain and frames.

    Each frame carries its file, line and function, the source lines around
    the one that ran, and its local variables as plain data — two levels deep,
    so a large object does not swell the profile. The exceptions it was
    raised from, or while handling, follow it, as Python itself prints them.
    """

    __slots__ = ()

    @property
    def name(self) -> str:
        """``"exception"``."""
        return _NAME

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        """Return the exception, or that there was none."""
        exception = profiled.exception
        if exception is None:
            return {"has_exception": False}
        return {
            "has_exception": True,
            "status_code": profiled.status_code,
            "chain": [_describe(error) for error in _chain(exception)],
        }


def _chain(exception: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    current: BaseException | None = exception
    while current is not None and current not in chain and len(chain) < _MAX_CHAIN:
        chain.append(current)
        cause = current.__cause__
        current = (
            cause if cause is not None or current.__suppress_context__ else current.__context__
        )
    return chain


def _describe(exception: BaseException) -> dict[str, object]:
    klass = type(exception)
    return {
        "class": f"{klass.__module__}.{klass.__qualname__}"
        if klass.__module__ != "builtins"
        else klass.__qualname__,
        "message": str(exception),
        "frames": _frames(exception.__traceback__),
    }


def _frames(trace: TracebackType | None) -> list[dict[str, object]]:
    frames: list[dict[str, object]] = []
    for frame, line in traceback.walk_tb(trace):
        code = frame.f_code
        first = max(1, line - _CONTEXT_LINES)
        frames.append(
            {
                "file": code.co_filename,
                "line": line,
                "function": code.co_qualname,
                "code": [
                    {
                        "number": number,
                        "text": linecache.getline(code.co_filename, number).rstrip("\n"),
                    }
                    for number in range(first, line + _CONTEXT_LINES + 1)
                    if linecache.getline(code.co_filename, number)
                ],
                "locals": {
                    name: clone_var(value, max_depth=2, max_items=30, max_string=300)
                    for name, value in cast("dict[str, object]", frame.f_locals).items()
                },
            }
        )
    # The innermost frames are where it happened, and the ones kept past the limit.
    return frames[-_MAX_FRAMES:]
