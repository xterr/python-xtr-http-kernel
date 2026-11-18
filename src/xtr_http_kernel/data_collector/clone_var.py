"""Any value, as plain data a profile can keep and a page can show."""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import PurePath
from typing import Final, cast, final
from uuid import UUID

__all__ = ["clone_var"]

_BYTES_SHOWN: Final = 64
_SCALAR_AS_TEXT: Final = (date, datetime, time, timedelta, Decimal, UUID, PurePath)


def clone_var(
    value: object,
    *,
    max_depth: int = 4,
    max_items: int = 100,
    max_string: int = 1000,
) -> dict[str, object]:
    """Return ``value`` as a tree of plain data, cut where it grows too large.

    A profile is written as JSON and read back by another process, so what a
    collector keeps of a live object is a description of it: every node is a
    mapping with a ``kind`` and the ``type`` it was —

    - ``scalar``: ``None``, a boolean, a number, an enum member, a date or time,
      a decimal, a UUID or a path, under ``value`` (text where JSON has no
      such value);
    - ``str``: the text under ``value``, ``truncated`` the characters cut;
    - ``bytes``: the ``length`` and a hex ``value`` of the first bytes;
    - ``mapping``: ``items``, a list of ``[key, value]`` node pairs;
    - ``sequence``: ``items``, a list of nodes — a list, tuple, set or any other
      sized iterable of the standard kinds;
    - ``object``: ``attributes``, a list of ``[name, node]`` pairs read from
      the instance's ``__dict__`` and ``__slots__`` — never through a property;
    - ``cut``: a node left out, past ``max_depth`` or already open above it
      (``reason`` is ``"depth"`` or ``"recursion"``).

    ``truncated`` on a mapping, sequence or object counts the items left out
    past ``max_items``.
    """
    return _Cloner(max_depth, max_items, max_string).clone(value, 0)


@final
class _Cloner:
    __slots__ = ("_max_depth", "_max_items", "_max_string", "_open")

    def __init__(self, max_depth: int, max_items: int, max_string: int) -> None:
        self._max_depth = max_depth
        self._max_items = max_items
        self._max_string = max_string
        self._open: set[int] = set()

    def clone(self, value: object, depth: int) -> dict[str, object]:  # noqa: PLR0911 — one return per kind
        type_name = _type_name(value)
        if value is None or isinstance(value, bool | int):
            return {"kind": "scalar", "type": type_name, "value": value}
        if isinstance(value, float):
            shown: object = value if math.isfinite(value) else repr(value)
            return {"kind": "scalar", "type": type_name, "value": shown}
        if isinstance(value, Enum):
            return {
                "kind": "scalar",
                "type": type_name,
                "value": f"{type(value).__name__}.{value.name}",
            }
        if isinstance(value, _SCALAR_AS_TEXT):
            return {"kind": "scalar", "type": type_name, "value": str(value)}
        if isinstance(value, str):
            return {
                "kind": "str",
                "type": type_name,
                "value": value[: self._max_string],
                "truncated": max(0, len(value) - self._max_string),
            }
        if isinstance(value, bytes | bytearray | memoryview):
            raw = bytes(cast("bytes | bytearray | memoryview[int]", value))
            return {
                "kind": "bytes",
                "type": type_name,
                "length": len(raw),
                "value": raw[:_BYTES_SHOWN].hex(),
                "truncated": max(0, len(raw) - _BYTES_SHOWN),
            }
        if depth >= self._max_depth:
            return {"kind": "cut", "type": type_name, "reason": "depth"}
        if id(value) in self._open:
            return {"kind": "cut", "type": type_name, "reason": "recursion"}
        self._open.add(id(value))
        try:
            return self._container(value, type_name, depth + 1)
        finally:
            self._open.discard(id(value))

    def _container(self, value: object, type_name: str, depth: int) -> dict[str, object]:
        if isinstance(value, Mapping):
            pairs = list(cast("Mapping[object, object]", value).items())
            return {
                "kind": "mapping",
                "type": type_name,
                "items": [
                    [self.clone(key, depth), self.clone(item, depth)]
                    for key, item in pairs[: self._max_items]
                ],
                "truncated": max(0, len(pairs) - self._max_items),
            }
        if isinstance(value, list | tuple | AbstractSet):
            items = list(cast("list[object] | tuple[object, ...] | AbstractSet[object]", value))
            return {
                "kind": "sequence",
                "type": type_name,
                "items": [self.clone(item, depth) for item in items[: self._max_items]],
                "truncated": max(0, len(items) - self._max_items),
            }
        attributes = _attributes(value)
        return {
            "kind": "object",
            "type": type_name,
            "attributes": [
                [name, self.clone(item, depth)] for name, item in attributes[: self._max_items]
            ],
            "truncated": max(0, len(attributes) - self._max_items),
        }


def _attributes(value: object) -> list[tuple[str, object]]:
    """Return the instance's own state, from ``__dict__`` and ``__slots__``, never a property."""
    found: dict[str, object] = {}
    instance_dict = cast("dict[str, object] | None", getattr(value, "__dict__", None))
    if isinstance(instance_dict, dict):
        found.update(instance_dict)
    for klass in type(value).__mro__:
        slots = cast("object", vars(klass).get("__slots__", ()))
        names = (slots,) if isinstance(slots, str) else cast("tuple[str, ...]", slots)
        for name in names:
            if name in {"__dict__", "__weakref__"} or name in found:
                continue
            missing = object()
            item: object = getattr(value, name, missing)
            if item is not missing:
                found[name] = item
    if isinstance(value, BaseException) and "args" not in found:
        found["args"] = value.args
    return list(found.items())


def _type_name(value: object) -> str:
    klass = type(value)
    if klass.__module__ == "builtins":
        return klass.__qualname__
    return f"{klass.__module__}.{klass.__qualname__}"
