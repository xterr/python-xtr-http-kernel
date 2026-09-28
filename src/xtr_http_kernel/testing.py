"""Swapping services in a served application, for the span of a test.

The setup call builds a kernel at every start of the application's
lifespan; :func:`override_services` parks a mapping on the application for
those builds to apply, so every boot hook and every route already sees the
replacements. Enter the block before starting the application's lifespan.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from ._state import OVERRIDES_KEY

if TYPE_CHECKING:
    from collections.abc import Generator, Hashable, Mapping

    from fastapi import FastAPI

__all__ = ["override_services"]


@contextmanager
def override_services(
    app: FastAPI,
    overrides: Mapping[type | tuple[type, Hashable], object],
    /,
) -> Generator[None, None, None]:
    """Serve ``app`` with ``overrides`` while the block is entered.

    A key is a type, or a ``(type, qualifier)`` pair for a qualified
    service — the same keys ``apply_overrides`` takes. The mapping applies
    to every kernel built while the block is entered; on exit the previous
    overrides, if any, are restored::

        with override_services(app, {Mailer: FakeMailer()}):
            ...  # every application life started here sees the fake

    Args:
        app: The application the setup call serves.
        overrides: What to replace, keyed by type or ``(type, qualifier)``.
    """
    previous: object = getattr(app.state, OVERRIDES_KEY, None)
    setattr(app.state, OVERRIDES_KEY, dict(overrides))
    try:
        yield
    finally:
        if previous is None:
            delattr(app.state, OVERRIDES_KEY)
        else:
            setattr(app.state, OVERRIDES_KEY, previous)
