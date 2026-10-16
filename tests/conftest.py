"""Shared test fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from starlette.requests import Request
from xtr_http_message import ServerRequest

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from xtr_http_message_contracts import ServerRequestInterface


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


@pytest.fixture
def server_request() -> ServerRequestInterface:
    # The events carry a request as a message; a plain one stands in for the
    # served request wherever a unit test only reads what the message says.
    return ServerRequest(
        "GET",
        "http://bookshop.test/books/978-0141439518?quantity=2",
        {"Host": "bookshop.test"},
    )


@pytest.fixture
def state() -> MutableMapping[str, object]:
    # The per-request bag the events carry, empty as a request's starts.
    return {}
