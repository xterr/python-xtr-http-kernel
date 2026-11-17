"""The listeners this library ships for its own lifecycle.

Each contributes one of the things every application wants around an
endpoint: a request id, an uncaught exception in the log, a header keeping a
page out of a search index. The bundle registers them; outside a container
each is an ordinary object to register by hand.
"""

from __future__ import annotations

from .disallow_robots_indexing_listener import DisallowRobotsIndexingListener
from .error_logging_listener import ErrorLoggingListener
from .request_id_listener import RequestIdListener

__all__ = [
    "DisallowRobotsIndexingListener",
    "ErrorLoggingListener",
    "RequestIdListener",
]
