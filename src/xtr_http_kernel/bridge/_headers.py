"""Headers either side of the bridge: a message's, and the wire's.

A message holds each name once with every value under it, in the case the
name arrived in; the wire holds one pair of bytes per value, lowercased. Both
directions live here so that the three places that cross agree on the
translation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from xtr_http_message_contracts import MessageInterface

__all__ = ["grouped_headers", "raw_headers", "with_raw_headers"]

_M = TypeVar("_M", bound="MessageInterface")


def raw_headers(message: MessageInterface) -> list[tuple[bytes, bytes]]:
    """Return a message's headers as the wire wants them: one pair per value.

    Names are lowercased, which is what every reader of a wire header
    expects and what lets a view of these pairs find a header by any case.

    Args:
        message: The message to read.

    Returns:
        One pair of bytes per value, in the order the message holds them.
    """
    return [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, values in message.get_headers().items()
        for value in values
    ]


def grouped_headers(raw: Iterable[tuple[bytes, bytes]]) -> Mapping[str, list[str]]:
    """Return each header name once, mapped to every value sent under it.

    Names are matched without regard to case and kept in the case they first
    arrived in, so a header sent twice is recorded once with both values
    rather than twice with the second replacing the first.

    Args:
        raw: The pairs of bytes as they came off the wire.

    Returns:
        Each name mapped to its values, in the order they arrived.
    """
    first_case: dict[str, str] = {}
    grouped: dict[str, list[str]] = {}
    for name, value in raw:
        header = name.decode("latin-1")
        canonical = first_case.setdefault(header.lower(), header)
        grouped.setdefault(canonical, []).append(value.decode("latin-1"))

    return grouped


def with_raw_headers(message: _M, raw: Iterable[tuple[bytes, bytes]]) -> _M:
    """Return ``message`` carrying ``raw`` and no other header.

    Args:
        message: The message to change.
        raw: The pairs of bytes the new message's headers are to be.

    Returns:
        A new message; the one passed in is left as it was.

    Raises:
        ValueError: When one of the pairs is not a header name and value.
    """
    replaced = message
    for name in list(message.get_headers()):
        replaced = replaced.without_header(name)

    for name, values in grouped_headers(raw).items():
        replaced = replaced.with_header(name, values)

    return replaced
