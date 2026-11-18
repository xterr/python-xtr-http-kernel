"""The tag a bundle puts on a data collector."""

from __future__ import annotations

from typing import Final

__all__ = ["DATA_COLLECTOR_TAG"]

DATA_COLLECTOR_TAG: Final = "http_kernel.data_collector"
"""Marks a :class:`~xtr_http_kernel.data_collector.DataCollectorInterface` service for the profiler.

Its attributes:

- ``name`` — what the collector's data is kept under, equal to the collector's
  own ``name``;
- ``template`` — the template its panel is shown with, as
  ``"@<import package>/<path under its templates folder>"``;
- ``priority`` — an integer, ``0`` when absent: higher comes first, in the
  toolbar and in the profile's menu; ties keep registration order.

```python
services.set(QueryCollector).add_tag(
    DATA_COLLECTOR_TAG, name="orm", template="@xtr_orm/collector/orm.html.j2", priority=250
)
```
"""
