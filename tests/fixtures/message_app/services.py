"""A per-request service that takes the request message through its constructor.

Nothing in it reaches for the framework: it is the kind of service a library
written against the message contract would ship, and the container hands it
the same request the route is holding.
"""

from __future__ import annotations

from typing import Final, final

# Read at runtime: the container fills the constructor parameter below.
from xtr_dependency_injection import as_service
from xtr_http_message_contracts import ServerRequestInterface

BUILDS: Final[list[int]] = []
"""The identity of every audit built, so a test can count them per request."""


@final
@as_service(lifetime="scoped")
class RequestAudit:
    """Reads the request once per request scope."""

    def __init__(self, request: ServerRequestInterface) -> None:
        self.request: ServerRequestInterface = request
        BUILDS.append(id(self))

    def path(self) -> str:
        """Return the path the request asked for."""
        return self.request.get_uri().get_path()
