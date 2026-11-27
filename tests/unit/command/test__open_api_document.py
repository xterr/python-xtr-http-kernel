"""Unit tests for the reshaping of an OpenAPI description before it is exported."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import pytest

from xtr_http_kernel.command._open_api_document import filter_tags, for_api_gateway
from xtr_http_kernel.exception import InvalidArgumentError

if TYPE_CHECKING:
    from xtr_http_kernel.command._open_api_document import JsonValue


def _document() -> dict[str, JsonValue]:
    return {
        "openapi": "3.1.0",
        "tags": [{"name": "books"}, {"name": "orders"}],
        "paths": {
            "/books/{isbn}": {
                "summary": "One book",
                "parameters": [
                    {"name": "isbn", "in": "path"},
                    {"name": "x trace", "in": "header"},
                ],
                "get": {
                    "tags": ["books"],
                    "parameters": [
                        {"name": "fields[]", "in": "query"},
                        {"$ref": "#/components/parameters/Locale"},
                    ],
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "anyOf": [{"$ref": "#/components/schemas/Page_Book_"}]
                                    }
                                }
                            }
                        }
                    },
                },
                "delete": {"tags": ["orders"]},
            },
            "/orders": {"post": {"tags": ["orders"]}},
        },
        "components": {
            "schemas": {
                "Page_Book_": {
                    "properties": {
                        "items": {"items": {"$ref": "#/components/schemas/Book"}},
                        "id": {"type": "string", "readOnly": True},
                    }
                },
                "Book": {"properties": {"isbn": {"type": "string"}}},
            }
        },
    }


def test_filter_tags_keeps_the_operations_of_those_tags_and_what_describes_their_path() -> None:
    filtered = filter_tags(_document(), ["books"])

    assert filtered["paths"] == {
        "/books/{isbn}": {
            key: value
            for key, value in _paths(_document())["/books/{isbn}"].items()
            if key != "delete"
        }
    }
    assert filtered["tags"] == [{"name": "books"}]


def test_filter_tags_without_a_match_keeps_no_path() -> None:
    assert filter_tags(_document(), ["authors"])["paths"] == {}


def test_a_gateway_name_keeps_letters_and_digits_and_every_reference_follows() -> None:
    gateway = for_api_gateway(_document())

    schemas = _object(_object(gateway["components"])["schemas"])
    assert list(schemas) == ["PageBook", "Book"]
    operation = _object(_paths(gateway)["/books/{isbn}"]["get"])
    content = _object(_object(_object(operation["responses"])["200"])["content"])
    assert _object(content["application/json"])["schema"] == {
        "anyOf": [{"$ref": "#/components/schemas/PageBook"}]
    }


def test_a_gateway_drops_the_parameters_it_cannot_name_and_keeps_references() -> None:
    gateway = for_api_gateway(_document())

    item = _paths(gateway)["/books/{isbn}"]
    assert item["parameters"] == [{"name": "isbn", "in": "path"}]
    assert _object(item["get"])["parameters"] == [{"$ref": "#/components/parameters/Locale"}]


def test_a_gateway_takes_read_only_off_every_property() -> None:
    gateway = for_api_gateway(_document())

    page = _object(_object(_object(gateway["components"])["schemas"])["PageBook"])
    assert _object(page["properties"])["id"] == {"type": "string"}


def test_two_schemas_a_gateway_would_name_alike_are_refused() -> None:
    document = _document()
    _object(_object(document["components"])["schemas"])["PageBook"] = {}

    with pytest.raises(InvalidArgumentError, match='"Page_Book_" and "PageBook"'):
        _ = for_api_gateway(document)


def test_the_given_description_is_left_as_it_was() -> None:
    document = _document()
    before = copy.deepcopy(document)

    _ = filter_tags(document, ["orders"])
    _ = for_api_gateway(document)

    assert document == before


def _object(value: JsonValue) -> dict[str, JsonValue]:
    assert isinstance(value, dict)
    return value


def _paths(document: dict[str, JsonValue]) -> dict[str, dict[str, JsonValue]]:
    return {path: _object(item) for path, item in _object(document["paths"]).items()}
