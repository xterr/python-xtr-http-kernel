"""The request as it arrived and the response head it got."""

from __future__ import annotations

import shlex
from collections.abc import Mapping
from typing import TYPE_CHECKING, Final, cast, final

from xtr_http_kernel.profiler import _state_keys as keys

from ._masking import is_sensitive_field, masked_field, masked_header
from .clone_var import clone_var

if TYPE_CHECKING:
    from .profiled_request import ProfiledRequest

__all__ = ["RequestDataCollector"]

_NAME: Final = "request"


@final
class RequestDataCollector:
    """Keeps the request's head, its parameters, its state and the response's head.

    Credentials never reach a profile: the ``Authorization``, ``Cookie`` and
    ``Set-Cookie`` headers, and every parameter, field or cookie whose name
    holds ``password``, ``secret`` or ``token``, are kept as ``******``.

    The body is never read for this: a parsed body is kept only when the
    application already read and parsed it. Once the response has left, a
    ``curl`` command replaying the request is added.
    """

    __slots__ = ()

    @property
    def name(self) -> str:
        """``"request"``."""
        return _NAME

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        """Return the request and response heads, parameters and state."""
        request = profiled.request
        uri = request.get_uri()
        parsed = request.get_parsed_body()
        return {
            "method": request.get_method(),
            "uri": str(uri),
            "path": uri.get_path(),
            "protocol_version": request.get_protocol_version(),
            "request_headers": {
                name: masked_header(name, ", ".join(values))
                for name, values in request.get_headers().items()
            },
            "query": _fields(request.get_query_params()),
            "cookies": _fields(request.get_cookie_params()),
            "attributes": {
                str(name): clone_var(value) for name, value in request.get_attributes().items()
            },
            "body": (
                _fields(cast("Mapping[str, object]", parsed))
                if isinstance(parsed, Mapping)
                else (clone_var(parsed) if parsed is not None else None)
            ),
            "state": {
                name: clone_var(value, max_depth=3)
                for name, value in profiled.state.items()
                if not name.startswith(keys.PREFIX)
            },
            "request_id": profiled.state.get("request_id"),
            "status_code": profiled.status_code,
            "response_headers": {
                name: masked_header(name, value) for name, value in profiled.headers.items()
            },
            "content_type": profiled.headers.get("content-type", ""),
        }

    def late_collect(self, data: dict[str, object], profiled: ProfiledRequest) -> dict[str, object]:
        """Add a ``curl`` command replaying the request, credentials masked."""
        request = profiled.request
        parts = ["curl", "-X", request.get_method(), str(request.get_uri())]
        for name, values in request.get_headers().items():
            parts.extend(["-H", f"{name}: {masked_header(name, ', '.join(values))}"])
        return {**data, "curl_command": shlex.join(parts)}


def _fields(values: Mapping[str, object]) -> dict[str, object]:
    """Return ``values`` as plain data, the likely credentials masked."""
    return {
        str(name): (
            masked_field(str(name), str(value))
            if is_sensitive_field(str(name))
            else (value if isinstance(value, str) else clone_var(value, max_depth=2))
        )
        for name, value in values.items()
    }
