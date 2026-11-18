"""Where profiles are kept between the request that made them and the page that shows them."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable

    from .profile import Profile
    from .profile_summary import ProfileSummary

__all__ = ["ProfilerStorageInterface"]


@runtime_checkable
class ProfilerStorageInterface(Protocol):
    """Writes profiles, reads one back by token, and searches what it holds.

    Every method blocks: an async caller runs them in a worker thread, so a
    profile written as a request ends never holds up the next one.
    """

    def find(  # noqa: PLR0913 — every search filter is its own keyword
        self,
        ip: str | None,
        url: str | None,
        limit: int,
        method: str | None,
        *,
        start: int | None = None,
        end: int | None = None,
        status_code: int | None = None,
        filter: Callable[[ProfileSummary], bool] | None = None,  # noqa: A002 — the filter is what it is
    ) -> list[ProfileSummary]:
        """Return up to ``limit`` stored profiles, newest first, matching every filter given.

        Args:
            ip: Part of the client address.
            url: Part of the URL; with a leading ``!``, a part the URL must not hold.
            limit: How many to return at most.
            method: Part of the method.
            start: The earliest time, in seconds since the epoch.
            end: The latest time, in seconds since the epoch.
            status_code: The exact status.
            filter: Applied to each candidate last.
        """
        ...

    def read(self, token: str) -> Profile | None:
        """Return the profile stored under ``token``, or ``None``.

        Raises:
            InvalidTokenError: When ``token`` is not a valid token.
        """
        ...

    def write(self, profile: Profile) -> bool:
        """Store ``profile``, replacing one stored under the same token; tell whether it was."""
        ...

    def purge(self) -> None:
        """Remove every stored profile."""
        ...
