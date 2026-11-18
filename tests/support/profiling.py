"""Building what a data collector is handed, without serving anything."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_message import ServerRequest

from xtr_http_kernel.data_collector import ProfiledRequest

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["profiled"]


def profiled(  # noqa: PLR0913 — one keyword per part a test varies
    method: str = "GET",
    uri: str = "http://shop.test/books?q=dune",
    *,
    headers: Mapping[str, str] | None = None,
    status_code: int = 200,
    response_headers: Mapping[str, str] | None = None,
    state: Mapping[str, object] | None = None,
    exception: BaseException | None = None,
) -> ProfiledRequest:
    """Return a profiled request over a plain message."""
    request = ServerRequest(
        method,
        uri,
        dict(headers or {}),
        server_params={"client": ("127.0.0.1", 5000), "server": ("shop.test", 80)},
    )
    return ProfiledRequest(
        request, status_code, dict(response_headers or {}), dict(state or {}), exception
    )
