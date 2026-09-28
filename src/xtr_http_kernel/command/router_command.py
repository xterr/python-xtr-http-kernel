"""What both router commands share: finding the application to report on."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, ClassVar, Final, cast

from fastapi import FastAPI

from xtr_http_kernel.bundle.http_kernel_config import HttpKernelConfig

if TYPE_CHECKING:
    from xtr_console import ConsoleStyle

__all__ = ["RouterCommand"]

_ZERO_CONFIG: Final = HttpKernelConfig()
"""What a console without a container builds these commands with."""

_NO_APPLICATION: Final = (
    'no application to read: pass --app "package.module:app", or name one on the '
    "http kernel's configuration"
)


class RouterCommand:
    """A command reporting on an application, named on the command line or configured.

    A container builds it with the http kernel's configuration, so an
    application that names its own needs no option. Without a container the
    console builds it bare, and ``--app`` is the only way to name one.

    Nothing is imported until a command runs, and the application is only
    read: no server starts, and no route is touched.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_config",)

    _config: HttpKernelConfig

    def __init__(self, config: HttpKernelConfig = _ZERO_CONFIG) -> None:
        """Report on the application ``config`` names, unless an option overrides it."""
        self._config = config

    def _app_or_report(self, io: ConsoleStyle, app: str | None) -> FastAPI | None:
        """Import the application ``app`` names, or say on ``io`` why there is none.

        ``app`` is the command line's answer and wins; the configuration's
        is used when it is ``None``.
        """
        reference = app if app is not None else self._config.app
        if reference is None:
            io.error(_NO_APPLICATION)
            return None
        module_name, _, attribute = reference.partition(":")
        if not module_name or not attribute:
            io.error(f'an application reads "package.module:app", not {reference!r}')
            return None
        try:
            module = import_module(module_name)
        except ImportError as error:
            io.error(f"cannot import {module_name!r}: {error}")
            return None
        # A module attribute is whatever the module put there: the check below decides.
        loaded = cast("object", getattr(module, attribute, None))
        if not isinstance(loaded, FastAPI):
            io.error(f"{reference!r} does not name an application")
            return None
        return loaded
