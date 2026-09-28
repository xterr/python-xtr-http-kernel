"""Shared test fixtures."""

from __future__ import annotations

import pytest
from starlette.requests import Request


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def http_request() -> Request:
    # The smallest scope a request reads: enough for its method, url and
    # headers, and nothing a server would add that the lifecycle ignores.
    # Built by hand rather than through a client so the suite never runs an
    # application to get at a request.
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/books/978-0141439518",
            "raw_path": b"/books/978-0141439518",
            "root_path": "",
            "query_string": b"quantity=2",
            "headers": [(b"host", b"bookshop.test")],
            "client": ("127.0.0.1", 51234),
            "server": ("bookshop.test", 80),
        }
    )
