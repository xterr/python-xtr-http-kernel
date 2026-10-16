"""Storing what the scan found for routing, while the kernel compiles."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_dependency_injection import CompilerPassInterface

from xtr_http_kernel.routing.route_registry import ROUTE_REGISTRY_PARAMETER, RouteRegistry

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from fastapi import APIRouter
    from xtr_dependency_injection import ContainerBuilder

    from xtr_http_kernel.routing.decorator.as_routes import RoutesFile

__all__ = ["ROUTE_REGISTRY_PARAMETER", "RouteRegistryPass"]


@final
class RouteRegistryPass(CompilerPassInterface):
    """Stores the route resources and routes files the bundle collected.

    A pass rather than a bundle hook because the autoconfiguration callbacks
    that collect both run after every hook: only here is the scan's harvest
    complete. Nothing is called and nothing is mounted while the kernel
    compiles — ``setup`` reads the parameter, stages the resources, and runs
    the files, and only what a file includes is served.
    """

    __slots__ = ("_files", "_resources")

    _resources: Sequence[tuple[str, Callable[[APIRouter], None]]]
    _files: Sequence[RoutesFile]

    def __init__(
        self,
        resources: Sequence[tuple[str, Callable[[APIRouter], None]]],
        files: Sequence[RoutesFile],
    ) -> None:
        """Hold the bundle's lists, read in :meth:`process` — the callbacks fill them after this."""
        self._resources = resources
        self._files = files

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Store the registry under its parameter."""
        builder.set_parameter(
            ROUTE_REGISTRY_PARAMETER,
            RouteRegistry(tuple(self._resources), tuple(self._files)),
        )
        builder.log(
            self,
            f"Collected {len(self._resources)} route resource function(s) and "
            f"{len(self._files)} routes file(s).",
        )
