"""Reshaping an OpenAPI description before it is exported: by tag, or for an API gateway.

Each function returns a new description and leaves the one it is given as it
was: the application keeps the description it built, and hands that same
object to every later caller.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from xtr_http_kernel.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

__all__ = ["JsonValue", "filter_tags", "for_api_gateway"]

type JsonValue = dict[str, JsonValue] | list[JsonValue] | str | int | float | bool | None
"""A value of a JSON document."""

_OPERATIONS: Final = frozenset(
    {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
)
"""The keys of a path item that hold an operation; the others describe the path."""

_GATEWAY_PARAMETER_NAME: Final = re.compile(r"[a-zA-Z0-9._$-]+")
_NOT_ALPHANUMERIC: Final = re.compile(r"[^0-9A-Za-z]")
_SCHEMA_REFERENCE: Final = "#/components/schemas/"


def filter_tags(document: dict[str, JsonValue], tags: Collection[str]) -> dict[str, JsonValue]:
    """Return ``document`` with only the operations carrying one of ``tags``.

    A path left without an operation goes too, and so does the description
    of every tag not asked for. Schemas only the dropped operations used stay:
    they are harmless, and finding them means following every reference.
    """
    wanted = frozenset(tags)
    paths: dict[str, JsonValue] = {}
    for path, item in _object(document.get("paths")).items():
        kept = {
            key: value
            for key, value in _object(item).items()
            if key not in _OPERATIONS or not wanted.isdisjoint(_strings(_object(value).get("tags")))
        }
        if not _OPERATIONS.isdisjoint(kept):
            paths[path] = kept
    filtered: dict[str, JsonValue] = {**document, "paths": paths}
    if "tags" in document:
        filtered["tags"] = [
            tag for tag in _array(document["tags"]) if _object(tag).get("name") in wanted
        ]
    return filtered


def for_api_gateway(document: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Return ``document`` without what an Amazon API Gateway import refuses.

    A gateway names a schema with letters and digits alone, so every schema
    is renamed that way, and every reference to it follows. It takes a
    parameter name made of letters, digits and ``._$-`` only, so an operation
    loses any other parameter. It refuses ``readOnly`` on a property, so the
    properties of every schema lose it.

    Raises:
        InvalidArgumentError: If two schemas would take the same name.
    """
    names = _gateway_names(_object(_object(document.get("components")).get("schemas")))
    gateway = _object_with_references(document, names)
    components = _object(gateway.get("components"))
    if "schemas" in components:
        components["schemas"] = {
            names[name]: _without_read_only(schema)
            for name, schema in _object(components["schemas"]).items()
        }
    for item in _object(gateway.get("paths")).values():
        path_item = _object(item)
        _keep_gateway_parameters(path_item)
        for key, operation in path_item.items():
            if key in _OPERATIONS:
                _keep_gateway_parameters(_object(operation))
    return gateway


def _gateway_names(schemas: Mapping[str, JsonValue]) -> dict[str, str]:
    """Map each schema name to its letters and digits.

    Raises:
        InvalidArgumentError: If two names keep the same letters and digits.
    """
    names: dict[str, str] = {}
    owners: dict[str, str] = {}
    for name in schemas:
        renamed = _NOT_ALPHANUMERIC.sub("", name)
        if renamed in owners:
            reason = (
                f'the schemas "{owners[renamed]}" and "{name}" would both be named "{renamed}" '
                "for an API gateway, which names a schema with letters and digits alone"
            )
            raise InvalidArgumentError(reason)
        owners[renamed] = name
        names[name] = renamed
    return names


def _with_references(value: JsonValue, names: Mapping[str, str]) -> JsonValue:
    """Return a copy of ``value`` whose schema references use the names in ``names``."""
    if isinstance(value, dict):
        return _object_with_references(value, names)
    if isinstance(value, list):
        return [_with_references(item, names) for item in value]
    return value


def _object_with_references(
    value: dict[str, JsonValue], names: Mapping[str, str]
) -> dict[str, JsonValue]:
    copied = {key: _with_references(item, names) for key, item in value.items()}
    reference = copied.get("$ref")
    if isinstance(reference, str) and reference.startswith(_SCHEMA_REFERENCE):
        name = reference.removeprefix(_SCHEMA_REFERENCE)
        copied["$ref"] = _SCHEMA_REFERENCE + names.get(name, name)
    return copied


def _without_read_only(schema: JsonValue) -> JsonValue:
    """Return ``schema`` with ``readOnly`` taken off each of its properties."""
    if not isinstance(schema, dict) or not isinstance(schema.get("properties"), dict):
        return schema
    properties = {
        name: (
            {key: value for key, value in prop.items() if key != "readOnly"}
            if isinstance(prop, dict)
            else prop
        )
        for name, prop in _object(schema["properties"]).items()
    }
    return {**schema, "properties": properties}


def _keep_gateway_parameters(holder: dict[str, JsonValue]) -> None:
    """Drop from ``holder`` the parameters a gateway cannot name; a reference is kept."""
    parameters = holder.get("parameters")
    if not isinstance(parameters, list):
        return
    holder["parameters"] = [
        parameter
        for parameter in parameters
        if isinstance(parameter, dict)
        and (
            "$ref" in parameter
            or _GATEWAY_PARAMETER_NAME.fullmatch(str(parameter.get("name", ""))) is not None
        )
    ]


def _object(value: JsonValue) -> dict[str, JsonValue]:
    """Return ``value`` when it is a JSON object, else an empty one."""
    return value if isinstance(value, dict) else {}


def _array(value: JsonValue) -> list[JsonValue]:
    """Return ``value`` when it is a JSON array, else an empty one."""
    return value if isinstance(value, list) else []


def _strings(value: JsonValue) -> list[str]:
    """Return the strings of ``value`` when it is a JSON array."""
    return [item for item in _array(value) if isinstance(item, str)]
