"""Which route answered the request, and where a redirect pointed."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final, cast, final

from xtr_http_kernel.profiler import _state_keys as keys

if TYPE_CHECKING:
    from .profiled_request import ProfiledRequest

__all__ = ["RouterDataCollector"]

_NAME: Final = "router"
_REDIRECTION: Final = range(300, 400)


@final
class RouterDataCollector:
    """Keeps the matched route — name, path template, methods, endpoint, parameters.

    The route is noted on the request's state as its response starts, by the
    middleware the bundle puts just inside the lifecycle. A redirect also
    keeps where it pointed.
    """

    __slots__ = ()

    @property
    def name(self) -> str:
        """``"router"``."""
        return _NAME

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        """Return the matched route, and the target of a redirect."""
        route = profiled.state.get(keys.ROUTE)
        data: dict[str, object] = (
            dict(cast("Mapping[str, object]", route))
            if isinstance(route, Mapping)
            else {"matched": False, "path_params": {}}
        )
        data["redirect"] = (
            profiled.headers.get("location") if profiled.status_code in _REDIRECTION else None
        )
        return data
