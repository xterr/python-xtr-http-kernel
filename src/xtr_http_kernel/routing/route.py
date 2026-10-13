"""One route: where it answers, what answers it, and how the framework should treat it."""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass, field, replace
from typing import TYPE_CHECKING, final

from fastapi.datastructures import Default

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from enum import Enum

__all__ = ["Route"]


def _not_given() -> object:
    # The marker the framework itself uses for "no response model was named",
    # which differs from an explicit ``None`` (no response model at all).
    return Default(None)


@final
@dataclass(frozen=True, slots=True)
class Route:
    """One route of the table, keyed in its collection by name.

    A route carries no name of its own: the collection it sits in names it, so
    the same route can be added under another name, or renamed by prefixing
    every name of a collection, without being rebuilt.

    The options after ``endpoint`` are handed to the framework as they are, so a
    mounted route behaves exactly like the same function declared on a router.

    Attributes:
        path: Where the route answers, always with exactly one leading slash.
        endpoint: The function the framework calls; its parameters, injected
            ones included, are left untouched.
        methods: The HTTP methods it answers, upper-cased, each once.
        include_in_schema: Whether the generated API description lists it.
        tags: The groups the API description files it under.
        summary: The one-line description the API description shows.
        status_code: The status a successful answer carries.
        response_model: The model the answer is validated against; left
            unnamed, the framework reads it off the endpoint's return type,
            and ``None`` turns that off.
    """

    path: str
    endpoint: Callable[..., Awaitable[object]]
    _: KW_ONLY
    methods: tuple[str, ...] = ()
    include_in_schema: bool = True
    tags: tuple[str | Enum, ...] = ()
    summary: str | None = None
    status_code: int | None = None
    response_model: object = field(default_factory=_not_given, hash=False)

    def __post_init__(self) -> None:
        """Bring the path and the methods to their one written form."""
        object.__setattr__(self, "path", "/" + self.path.strip().lstrip("/"))
        object.__setattr__(self, "methods", tuple(dict.fromkeys(m.upper() for m in self.methods)))

    def with_path(self, path: str) -> Route:
        """Return this route answering at another path."""
        return replace(self, path=path)
