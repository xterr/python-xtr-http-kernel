"""The listeners this library ships for its own lifecycle.

Each contributes one of the things every application wants around an
endpoint: a request id, an uncaught exception in the log, a header keeping a
page out of a search index, a unit of work per request. The bundle registers
them; outside a container each is an ordinary object to register by hand.

:class:`~xtr_http_kernel.event_listener.log_unit_listener.LogUnitListener`
is not re-exported here: it needs the optional logging extra, so it is
imported from its own module by whoever knows that extra is installed.
"""

from __future__ import annotations

from .disallow_search_indexing_listener import DisallowSearchIndexingListener
from .error_logging_listener import ErrorLoggingListener
from .request_id_listener import RequestIdListener

__all__ = [
    "DisallowSearchIndexingListener",
    "ErrorLoggingListener",
    "RequestIdListener",
]
