"""Hands the profiler every tagged data collector, in panel order."""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from xtr_dependency_injection import CompilerPassInterface

from xtr_http_kernel.data_collector.data_collector_tag import DATA_COLLECTOR_TAG
from xtr_http_kernel.data_collector.data_collector_templates import DataCollectorTemplates
from xtr_http_kernel.exception.invalid_collector_priority_error import (
    InvalidCollectorPriorityError,
)
from xtr_http_kernel.exception.invalid_collector_tag_error import InvalidCollectorTagError
from xtr_http_kernel.profiler.profiler import Profiler

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceKey

__all__ = ["ProfilerPass"]


@final
class ProfilerPass(CompilerPassInterface):
    """Orders every ``http_kernel.data_collector`` service and gives the profiler them all.

    Highest ``priority`` first, a missing one counting as ``0``, ties in
    registration order. The profiler gets the services in that order, and
    :class:`~xtr_http_kernel.data_collector.DataCollectorTemplates` the
    ``(name, template)`` pairs, which is what shows the panels. A pass rather
    than a bundle hook, so the collectors every other bundle tagged are in.
    Nothing happens when the profiler is off — it is not registered then.
    """

    __slots__ = ()

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Set the profiler's collectors and the templates of their panels.

        Raises:
            InvalidCollectorTagError: When a tag lacks a ``name`` or a ``template``.
            InvalidCollectorPriorityError: When a tag's ``priority`` is not an integer.
        """
        if not builder.has_definition(Profiler):
            return
        entries: list[tuple[int, int, ServiceKey, str, str]] = []
        for order, (key, tags) in enumerate(
            builder.find_tagged_service_ids(DATA_COLLECTOR_TAG).items()
        ):
            attributes = tags[0]
            name = attributes.get("name")
            template = attributes.get("template")
            priority = attributes.get("priority", 0)
            if not isinstance(name, str) or not name:
                raise InvalidCollectorTagError(key, "name")
            if not isinstance(template, str) or not template:
                raise InvalidCollectorTagError(key, "template")
            if not isinstance(priority, int) or isinstance(priority, bool):
                raise InvalidCollectorPriorityError(key, priority)
            entries.append((priority, order, key, name, template))
        entries.sort(key=lambda entry: (-entry[0], entry[1]))
        _ = builder.get_definition(Profiler).set_argument(
            "keys", tuple(key for _, _, key, _, _ in entries)
        )
        _ = builder.get_definition(DataCollectorTemplates).set_argument(
            "entries", tuple((name, template) for _, _, _, name, template in entries)
        )
        builder.log(self, f"Handed the profiler {len(entries)} data collector(s).")
