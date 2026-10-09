"""The URI of a served request, read off the connection's own components."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_message.factory import HttpFactory

from xtr_http_kernel.bridge._scope_uri import scope_uri

if TYPE_CHECKING:
    from starlette.types import Scope


def _scope(**components: object) -> Scope:
    """Return a connection naming ``components``, with the usual rest."""
    return {
        "type": "http",
        "scheme": "http",
        "path": "/books",
        "query_string": b"",
        "headers": [],
        "server": ("bookshop.test", 80),
        **components,
    }


def _uri(**components: object) -> str:
    """Return the URI read off a connection naming ``components``, as text."""
    return str(scope_uri(HttpFactory(), _scope(**components)))


def test_the_uri_is_assembled_from_the_scheme_address_path_and_query() -> None:
    assert _uri(scheme="https", server=("bookshop.test", 443), query_string=b"page=2") == (
        "https://bookshop.test/books?page=2"
    )


def test_the_host_header_is_what_the_uri_names() -> None:
    assert _uri(headers=[(b"host", b"shelf.test")]) == "http://shelf.test/books"


def test_a_port_in_the_host_header_is_part_of_what_it_names() -> None:
    assert _uri(headers=[(b"host", b"shelf.test:8000")]) == "http://shelf.test:8000/books"


def test_the_standard_port_of_the_scheme_says_nothing_and_is_dropped() -> None:
    assert _uri(headers=[(b"host", b"shelf.test:80")]) == "http://shelf.test/books"


def test_an_address_of_the_long_kind_keeps_its_brackets() -> None:
    assert _uri(headers=[(b"host", b"[::1]:8000")]) == "http://[::1]:8000/books"


def test_an_address_of_the_long_kind_with_no_port_keeps_its_brackets() -> None:
    assert _uri(headers=[(b"host", b"[::1]")]) == "http://[::1]/books"


@pytest.mark.parametrize(
    "header",
    [
        pytest.param(b"::1", id="long-address-without-brackets"),
        pytest.param(b"shelf.test:books", id="port-that-is-not-a-number"),
        pytest.param(b"shelf.test:99999", id="port-no-connection-can-have"),
        pytest.param(b"shelf.test:", id="port-left-empty"),
    ],
)
def test_a_host_header_naming_no_host_leaves_the_listening_address_to_say(
    header: bytes,
) -> None:
    assert _uri(headers=[(b"host", header)]) == "http://bookshop.test/books"


def test_the_listening_address_stands_in_where_no_host_header_arrived() -> None:
    assert _uri(server=("shelf.test", 8000)) == "http://shelf.test:8000/books"


def test_a_listening_address_of_the_long_kind_is_given_its_brackets() -> None:
    assert _uri(server=("::1", 8000)) == "http://[::1]:8000/books"


def test_a_connection_naming_no_address_at_all_leaves_the_uri_without_one() -> None:
    # Pathological: a server names an address and HTTP/1.1 requires a host
    # header. The scheme is still known, so the URI keeps it and has no
    # authority at all — which reads back as the very same URI.
    assert _uri(server=None) == "http:/books"


def test_the_whole_target_path_is_the_path_of_the_uri() -> None:
    assert _uri(path="/mounted/books", root_path="/mounted") == "http://bookshop.test/mounted/books"


def test_the_query_string_arrives_as_it_was_sent() -> None:
    assert _uri(query_string=b"bar[baz]=42").endswith("?bar%5Bbaz%5D=42")


def test_a_scheme_the_connection_leaves_out_reads_as_the_plain_one() -> None:
    scope = _scope()
    del scope["scheme"]

    assert str(scope_uri(HttpFactory(), scope)).startswith("http://")
