"""An ordered, immutable chain of middleware factories, ready to wrap an app.

The http_kernel bundle builds one when the kernel is compiled: every
definition tagged ``http_kernel.middleware`` contributes a factory, ordered
by the tag's ``priority`` — highest first, so it wraps outermost and sees
the request first. The setup call fetches the stack once per application
life; the middleware it added composes the stack over the application.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

    from starlette.types import ASGIApp

    MiddlewareFactory = Callable[[ASGIApp], ASGIApp]

__all__ = ["MiddlewareStack"]


@final
class MiddlewareStack:
    """The middleware factories a kernel contributed, the outermost first.

    Immutable: built once when the kernel is compiled, composed as many
    times as the serving code asks.
    """

    __slots__ = ("_factories",)

    def __init__(self, factories: Iterable[MiddlewareFactory] = ()) -> None:
        """Hold ``factories`` in the given order — the outermost first."""
        self._factories = tuple(factories)

    def wrap(self, app: ASGIApp) -> ASGIApp:
        """Return ``app`` wrapped in every factory, the first one outermost."""
        wrapped = app
        # The first factory sits outermost, so it wraps last.
        for factory in reversed(self._factories):
            wrapped = factory(wrapped)
        return wrapped

    def __len__(self) -> int:
        """Return how many factories the stack holds."""
        return len(self._factories)

    def __iter__(self) -> Iterator[MiddlewareFactory]:
        """Yield the factories, the outermost first."""
        return iter(self._factories)
