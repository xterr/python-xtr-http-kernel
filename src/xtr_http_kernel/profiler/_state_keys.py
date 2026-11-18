"""Where the profiler keeps its notes on a request's state bag.

Every key starts with :data:`PREFIX`, so a collector listing the state
leaves the profiler's own entries out.
"""

from __future__ import annotations

from typing import Final

__all__ = ["CONTROLLER", "EXCEPTION", "PREFIX", "PROFILE", "ROUTE", "START", "TOKEN"]

PREFIX: Final = "_profiler."
START: Final = f"{PREFIX}start"
"""When the request arrived, in seconds since the epoch, as a float."""
EXCEPTION: Final = f"{PREFIX}exception"
"""What handling raised, when it raised."""
CONTROLLER: Final = f"{PREFIX}controller"
"""The stopwatch event spanning the application's own handling."""
PROFILE: Final = f"{PREFIX}profile"
"""The profile collected at the response, with what it was collected from."""
TOKEN: Final = f"{PREFIX}token"
"""The token of the request's profile, once it has one."""
ROUTE: Final = f"{PREFIX}route"
"""The route that answered, as plain data, once the response starts."""
