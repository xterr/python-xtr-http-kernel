"""The head of a stored profile, as a search lists it."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ProfileSummary"]


@dataclass(frozen=True, slots=True)
class ProfileSummary:
    """One stored profile as the index knows it, without its collectors' data.

    Attributes:
        token: What the profile is stored under.
        ip: The client's address.
        method: The request's method.
        url: The URL asked for.
        time: When it was profiled, in seconds since the epoch.
        status_code: The status the response carried.
        virtual_type: What kind of work it is a profile of.
        has_errors: Whether handling raised or anything logged an error.
    """

    token: str
    ip: str
    method: str
    url: str
    time: int
    status_code: int
    virtual_type: str
    has_errors: bool
