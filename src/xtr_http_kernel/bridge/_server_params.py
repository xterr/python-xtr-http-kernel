"""What the connection says about itself, as the request's environment.

A message's environment parameters are whatever the server knows about
the request besides the request itself. Here that is the connection as
the server described it, minus the entries that are the framework's own
machinery — the headers, the matched route, the application — which the
message carries in its own right or has no business repeating. One
rule, read wherever a request's head is built off a connection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

    from starlette.types import Scope

__all__ = ["_DEFAULT_PROTOCOL", "_server_params"]

_SERVER_PARAMS: Final = (
    "type",
    "http_version",
    "method",
    "scheme",
    "path",
    "root_path",
    "query_string",
    "server",
    "client",
)

_DEFAULT_PROTOCOL: Final = "1.1"


def _server_params(scope: Scope) -> Mapping[str, object]:
    """Return the connection's own entries, under the names the server gave them."""
    return {key: cast("object", scope[key]) for key in _SERVER_PARAMS if key in scope}
