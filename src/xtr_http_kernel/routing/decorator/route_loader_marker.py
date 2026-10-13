"""What ``@as_route_loader`` records on a class."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

__all__ = ["RouteLoaderMarker"]


@final
@dataclass(frozen=True, slots=True)
class RouteLoaderMarker:
    """What ``@as_route_loader`` records on a class.

    Attributes:
        resource: The name an application imports the loader's routes by.
        prefixable: Whether those routes may be moved under a path prefix;
            ``False`` for routes whose location a standard fixes.
    """

    resource: str
    prefixable: bool = True
