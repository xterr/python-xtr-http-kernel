"""The anchor of the panel listing a page's background requests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from .profiled_request import ProfiledRequest

__all__ = ["AjaxDataCollector"]

_NAME: Final = "ajax"


@final
class AjaxDataCollector:
    """Keeps nothing: the requests a page makes after loading are watched in the browser.

    It exists so the toolbar has a panel to list them in; the page records
    each request it sends and links it to the profile its response names.
    """

    __slots__ = ()

    @property
    def name(self) -> str:
        """``"ajax"``."""
        return _NAME

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        """Return nothing."""
        del profiled
        return {}
