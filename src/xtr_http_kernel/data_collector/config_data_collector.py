"""What the application runs on: Python, the xtr packages, the kernel's environment and bundles."""

from __future__ import annotations

import platform
import sys
from importlib.metadata import distributions
from typing import TYPE_CHECKING, Final, cast, final

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .profiled_request import ProfiledRequest

__all__ = ["ConfigDataCollector"]

_NAME: Final = "config"
_PREFIX: Final = "xtr-"


@final
class ConfigDataCollector:
    """Keeps the runtime: the Python version, every xtr package installed, the kernel's settings.

    The package list is read the first time a request is collected, and kept,
    because it does not change while the process runs — and building the
    collector stays free of any reading.
    """

    __slots__ = ("_bundles", "_debug", "_environment", "_packages")

    def __init__(self, environment: str, debug: bool, bundles: Mapping[str, str]) -> None:
        """Describe a kernel built for ``environment``, in ``debug`` mode, with ``bundles``.

        Args:
            environment: The kernel's environment.
            debug: Whether the kernel runs in debug mode.
            bundles: Every active bundle's name, mapped to its class.
        """
        self._environment = environment
        self._debug = debug
        self._bundles = dict(bundles)
        self._packages: dict[str, str] | None = None

    @property
    def name(self) -> str:
        """``"config"``."""
        return _NAME

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        """Return the runtime and the kernel's settings."""
        server = profiled.request.get_server_params().get("server")
        if self._packages is None:
            found: dict[str, str] = {}
            for distribution in distributions():
                name = str(cast("object", distribution.metadata["Name"]) or "")
                if name.startswith(_PREFIX):
                    found[name] = distribution.version
            self._packages = dict(sorted(found.items()))
        return {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": sys.platform,
            "environment": self._environment,
            "debug": self._debug,
            "bundles": dict(self._bundles),
            "packages": dict(self._packages),
            "server": (
                [str(part) for part in cast("tuple[object, ...]", server)]
                if isinstance(server, tuple | list)
                else None
            ),
        }
