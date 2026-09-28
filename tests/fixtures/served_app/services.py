"""Services the served application's routes inject.

The module-level journals let the tests observe what only happens inside the
container: which scoped instances were built, and when a scoped resource's
cleanup ran relative to the response leaving.
"""

from __future__ import annotations

# wireup reads the factory's return annotation at runtime, so ``Iterator``
# cannot be deferred into a ``TYPE_CHECKING`` block.
from collections.abc import Iterator  # noqa: TC003
from typing import Annotated

from xtr_dependency_injection import Autowire, as_service

LIVE_UNITS: list[RequestUnit] = []
"""Every scoped unit built, kept alive so their identities stay distinct."""

TRACKED_STEPS: list[str] = []
"""What happened around the tracked resource, in order."""


@as_service
class Greeter:
    """A singleton greeting through a kernel parameter."""

    def __init__(self, punctuation: Annotated[str, Autowire(param="served.punctuation")]) -> None:
        self.punctuation: str = punctuation

    def greet(self, name: str) -> str:
        return f"hello {name}{self.punctuation}"


@as_service(lifetime="scoped")
class RequestUnit:
    """One instance per request scope, journalled so a test can count them."""

    def __init__(self) -> None:
        LIVE_UNITS.append(self)


class Tracked:
    """What the tracked factory yields."""


@as_service(lifetime="scoped")
def tracked_resource() -> Iterator[Tracked]:
    """A scoped resource whose cleanup marks when its scope closed.

    The cleanup sits in a ``finally`` because a scope that closes on an
    error throws that error into the generator — and the tests want the
    mark on every path.
    """
    TRACKED_STEPS.append("open")
    try:
        yield Tracked()
    finally:
        TRACKED_STEPS.append("cleanup")
