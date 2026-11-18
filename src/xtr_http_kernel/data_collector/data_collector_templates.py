"""Which template shows each collector's panel, in panel order."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["DataCollectorTemplates"]


@dataclass(frozen=True, slots=True)
class DataCollectorTemplates:
    """Every tagged collector's name and template, highest priority first.

    Filled while the container is built, from the
    :data:`~xtr_http_kernel.data_collector.DATA_COLLECTOR_TAG` tags; what shows
    profiles reads it to know which panels exist and what draws each.

    Attributes:
        entries: ``(name, template)`` pairs, in the order panels are shown.
    """

    entries: tuple[tuple[str, str], ...] = ()

    def template_of(self, name: str) -> str | None:
        """Return the template of the collector ``name``, or ``None``."""
        for collector, template in self.entries:
            if collector == name:
                return template
        return None
