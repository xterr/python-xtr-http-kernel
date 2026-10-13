"""Defining one route of a routes file — or moving one by its name."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Self, final

from xtr_http_kernel.routing.exception.invalid_argument_error import InvalidArgumentError
from xtr_http_kernel.routing.route import Route

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from enum import Enum

    from xtr_http_kernel.routing.route_collection import RouteCollection

__all__ = ["RouteConfigurator"]


@final
class RouteConfigurator:
    """Defines one route under a name, applied when the routes file returns.

    A route needs an endpoint — unless its name is already in the table, from a
    bundle's routes imported earlier: then only what is set here changes and
    the rest is kept, which is how an application moves one bundle route to
    another path without restating its endpoint. Either way the new definition
    replaces the old one under that name.
    """

    __slots__ = ("_changes", "_endpoint", "_name", "_path", "_priority")

    _name: str
    _path: str
    _endpoint: Callable[..., Awaitable[object]] | None
    _changes: dict[str, object]
    _priority: int | None

    def __init__(self, name: str, path: str) -> None:
        """Start the route ``name`` at ``path``."""
        self._name = name
        self._path = path
        self._endpoint = None
        self._changes = {}
        self._priority = None

    def endpoint(self, endpoint: Callable[..., Awaitable[object]]) -> Self:
        """Set the function the framework calls."""
        self._endpoint = endpoint
        return self

    def methods(self, *methods: str) -> Self:
        """Set the HTTP methods the route answers."""
        self._changes["methods"] = methods
        return self

    def priority(self, priority: int) -> Self:
        """Move the route ahead of (or behind) the ones declared before it."""
        self._priority = priority
        return self

    def tags(self, *tags: str | Enum) -> Self:
        """Set the groups the API description files the route under."""
        self._changes["tags"] = tags
        return self

    def summary(self, summary: str) -> Self:
        """Set the one-line description the API description shows."""
        self._changes["summary"] = summary
        return self

    def status_code(self, status_code: int) -> Self:
        """Set the status a successful answer carries."""
        self._changes["status_code"] = status_code
        return self

    def include_in_schema(self, *, include: bool = True) -> Self:
        """Say whether the API description lists the route."""
        self._changes["include_in_schema"] = include
        return self

    def response_model(self, model: object) -> Self:
        """Set the model the answer is validated against; ``None`` turns validation off."""
        self._changes["response_model"] = model
        return self

    def apply_to(self, collection: RouteCollection) -> None:
        """Add the route to ``collection``, replacing whatever its name held.

        Raises:
            InvalidArgumentError: No endpoint was set and the name is new.
        """
        existing = collection.get(self._name)
        name = self._name
        # An alias stands for its target: moving or redefining it means the target.
        while (alias := collection.get_alias(name)) is not None:
            name = alias.id
        if existing is None:
            name = self._name
            if self._endpoint is None:
                raise InvalidArgumentError(
                    f'The route "{self._name}" has no endpoint, and no route of that name '
                    "exists to take one from."
                )
            existing = Route(self._path, self._endpoint)
        elif self._endpoint is not None:
            existing = replace(existing, endpoint=self._endpoint)
        priority = self._priority
        if priority is None:
            priority = collection.get_priority(name) or 0
        collection.add(name, replace(existing, path=self._path, **self._changes), priority)
