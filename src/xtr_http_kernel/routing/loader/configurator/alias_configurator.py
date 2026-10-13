"""Declaring another name for a route in a routes file."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

from xtr_http_kernel.routing.alias import Alias

if TYPE_CHECKING:
    from xtr_http_kernel.routing.route_collection import RouteCollection

__all__ = ["AliasConfigurator"]


@final
class AliasConfigurator:
    """Declares ``name`` as another name for ``target``, applied when the routes file returns."""

    __slots__ = ("_deprecation", "_name", "_target")

    _name: str
    _target: str
    _deprecation: tuple[str, str, str] | None

    def __init__(self, name: str, target: str) -> None:
        """Make ``name`` stand for ``target``."""
        self._name = name
        self._target = target
        self._deprecation = None

    def deprecate(self, package: str, version: str, message: str = "") -> Self:
        """Mark the alias deprecated; ``%alias_id%`` in ``message`` stands for its name.

        Raises:
            InvalidArgumentError: The message spans lines, contains ``*/``, or
                does not name the alias — refused here, where it is written.
        """
        _ = Alias(self._target).set_deprecated(package, version, message)
        self._deprecation = (package, version, message)
        return self

    def apply_to(self, collection: RouteCollection) -> None:
        """Add the alias to ``collection``."""
        stored = collection.add_alias(self._name, self._target)
        if self._deprecation is not None:
            _ = stored.set_deprecated(*self._deprecation)
