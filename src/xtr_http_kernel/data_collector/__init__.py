"""What a profile is made of: the collectors that pick a request's data up.

A collector implements :class:`DataCollectorInterface` — a name, and a
``collect`` that returns plain data — and, when it has more to keep once the
response has left, :class:`LateDataCollectorInterface`. A bundle registers it
tagged :data:`DATA_COLLECTOR_TAG`, naming it and the template its panel is
shown with.
"""

from __future__ import annotations

from .clone_var import clone_var
from .data_collector_interface import DataCollectorInterface
from .data_collector_tag import DATA_COLLECTOR_TAG
from .data_collector_templates import DataCollectorTemplates
from .late_data_collector_interface import LateDataCollectorInterface
from .profiled_request import ProfiledRequest
from .request_trace import RequestTrace
from .tracing_data_collector_interface import TracingDataCollectorInterface

__all__ = [
    "DATA_COLLECTOR_TAG",
    "DataCollectorInterface",
    "DataCollectorTemplates",
    "LateDataCollectorInterface",
    "ProfiledRequest",
    "RequestTrace",
    "TracingDataCollectorInterface",
    "clone_var",
]
