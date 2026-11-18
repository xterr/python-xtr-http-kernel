"""What the profiler kept of one request."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, cast, final, override

from xtr_http_kernel.exception.unknown_collector_error import UnknownCollectorError

__all__ = ["Profile"]

_REQUEST: Final = "request"


@final
class Profile:
    """One request as the profiler saw it: who asked, what came back, what each collector kept.

    The head — token, client address, method, URL, time, status — is what a
    search lists; :attr:`collectors` holds every collector's data under its
    name, plain data only, so a profile written as JSON reads back the same.

    Attributes:
        token: What the profile is stored and looked up under.
        ip: The address of the client that sent the request.
        method: The request's method.
        url: The URL the request asked for.
        time: When it was profiled, in seconds since the epoch.
        status_code: The status the response carried.
        virtual_type: What kind of work this is a profile of — ``"request"``
            unless the work was something else profiled the same way.
        has_errors: Whether handling raised, or anything logged an error.
        collectors: Each collector's data, under the collector's name.
    """

    __slots__ = (
        "collectors",
        "has_errors",
        "ip",
        "method",
        "status_code",
        "time",
        "token",
        "url",
        "virtual_type",
    )

    def __init__(  # noqa: PLR0913 — a profile's head is a fixed record of named fields
        self,
        token: str,
        *,
        ip: str = "",
        method: str = "",
        url: str = "",
        time: int = 0,
        status_code: int = 0,
        virtual_type: str = _REQUEST,
        has_errors: bool = False,
        collectors: Mapping[str, Mapping[str, object]] | None = None,
    ) -> None:
        """Make the profile stored under ``token``."""
        self.token = token
        self.ip = ip
        self.method = method
        self.url = url
        self.time = time
        self.status_code = status_code
        self.virtual_type = virtual_type
        self.has_errors = has_errors
        self.collectors: dict[str, Mapping[str, object]] = dict(collectors or {})

    def add_collector(self, name: str, data: Mapping[str, object]) -> None:
        """Keep ``data`` under the collector ``name``."""
        self.collectors[name] = data

    def has_collector(self, name: str) -> bool:
        """Tell whether a collector named ``name`` kept data in this profile."""
        return name in self.collectors

    def get_collector(self, name: str) -> Mapping[str, object]:
        """Return the data the collector ``name`` kept.

        Raises:
            UnknownCollectorError: When no collector of that name kept any.
        """
        data = self.collectors.get(name)
        if data is None:
            raise UnknownCollectorError(name, tuple(self.collectors))
        return data

    def to_dict(self) -> dict[str, object]:
        """Return the profile as plain data, ready to be written as JSON."""
        return {
            "token": self.token,
            "ip": self.ip,
            "method": self.method,
            "url": self.url,
            "time": self.time,
            "status_code": self.status_code,
            "virtual_type": self.virtual_type,
            "has_errors": self.has_errors,
            "collectors": {name: dict(data) for name, data in self.collectors.items()},
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Profile:
        """Rebuild a profile from what :meth:`to_dict` returned.

        A field of the wrong type reads as its default, so a profile written
        by another version is shown as far as it can be rather than refused.
        """
        collectors = data.get("collectors")
        return cls(
            _string(data, "token"),
            ip=_string(data, "ip"),
            method=_string(data, "method"),
            url=_string(data, "url"),
            time=_integer(data, "time"),
            status_code=_integer(data, "status_code"),
            virtual_type=_string(data, "virtual_type") or _REQUEST,
            has_errors=data.get("has_errors") is True,
            collectors=(
                {
                    str(name): cast("Mapping[str, object]", value)
                    for name, value in cast("Mapping[object, object]", collectors).items()
                    if isinstance(value, Mapping)
                }
                if isinstance(collectors, Mapping)
                else None
            ),
        )

    @override
    def __repr__(self) -> str:
        """Return the head of the profile."""
        return (
            f"{type(self).__name__}({self.token!r}, {self.method} {self.url}, "
            f"status={self.status_code})"
        )


def _string(data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    return value if isinstance(value, str) else ""


def _integer(data: Mapping[str, object], key: str) -> int:
    value = data.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0
