"""Profiles kept as compressed files, found through an index appended to as they arrive."""

from __future__ import annotations

import csv
import gzip
import io
import json
import os
import re
import secrets
import shutil
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast, final, override

from xtr_clock import SystemClock

from xtr_http_kernel.exception.invalid_token_error import InvalidTokenError

from .profile import Profile
from .profile_summary import ProfileSummary

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from xtr_clock import ClockInterface

__all__ = ["FileProfilerStorage"]

_TOKEN: Final = re.compile(r"[A-Za-z0-9_-]+")
_INDEX: Final = "index.csv"
_OFFSET: Final = "index.csv.offset"
_SUFFIX: Final = ".json.gz"
_CHUNK: Final = 1024
_FIELDS: Final = 9
_CLEANUP_ONE_IN: Final = 10
_DEFAULT_LIFETIME: Final = timedelta(days=2)


@final
class FileProfilerStorage:
    """Keeps each profile as a gzipped JSON file, and every profile's head in one index.

    A profile lives at ``<folder>/<last two token characters>/<the two before>/<token>.json.gz``,
    so no directory grows past a few hundred entries. ``index.csv`` gets one
    line per new profile, appended in one write, so lines from several worker
    processes never interleave; a search reads it from the end, newest first,
    and stops as soon as it has enough.

    Profiles older than ``lifetime`` are left out of every search, and about
    one write in ten also deletes them — from where the last sweep stopped,
    which ``index.csv.offset`` records.
    """

    __slots__ = ("_clock", "_folder", "_lifetime")

    def __init__(
        self,
        folder: str | Path,
        lifetime: timedelta = _DEFAULT_LIFETIME,
        clock: ClockInterface | None = None,
    ) -> None:
        """Keep profiles under ``folder``, each for ``lifetime``.

        Args:
            folder: Where the profiles and the index live; made on the first write.
            lifetime: How long a profile is kept.
            clock: What "now" is read from; :class:`~xtr_clock.SystemClock` by default.
        """
        self._folder = Path(folder)
        self._lifetime = lifetime
        self._clock: ClockInterface = clock if clock is not None else SystemClock()

    @property
    def folder(self) -> Path:
        """Where the profiles are kept."""
        return self._folder

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

        ``ip`` and ``method`` match a part, ``url`` a part or — with a leading
        ``!`` — the absence of one, ``start`` and ``end`` bound the time,
        ``status_code`` matches exactly, and ``filter`` is asked last.
        """
        index = self._folder / _INDEX
        if limit < 1 or not index.is_file():
            return []
        oldest = self._now() - int(self._lifetime.total_seconds())
        found: list[ProfileSummary] = []
        for line in _lines_backwards(index):
            entry = _parse(line)
            if entry is None:
                continue
            if entry.time < oldest:
                break
            if not _matches(
                entry, ip=ip, url=url, method=method, start=start, end=end, status_code=status_code
            ):
                continue
            if filter is not None and not filter(entry):
                continue
            found.append(entry)
            if len(found) >= limit:
                break
        return found

    def read(self, token: str) -> Profile | None:
        """Return the profile stored under ``token``, or ``None``.

        Raises:
            InvalidTokenError: When ``token`` is not a valid token.
        """
        path = self._path(token)
        if not path.is_file():
            return None
        data = cast("object", json.loads(gzip.decompress(path.read_bytes())))
        if not isinstance(data, dict):
            return None
        return Profile.from_dict(cast("dict[str, object]", data))

    def write(self, profile: Profile) -> bool:
        """Store ``profile``, replacing one stored under its token; a new one joins the index.

        The file is written beside its final name and moved into place, so a
        reader never sees half of it.

        Raises:
            InvalidTokenError: When the profile's token is not a valid token.
        """
        path = self._path(profile.token)
        is_new = not path.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        # default=str: a collector is meant to keep plain data, and one that slipped
        # an object through still writes rather than losing the whole profile.
        payload = json.dumps(profile.to_dict(), separators=(",", ":"), default=str)
        staged = path.with_name(f"{path.name}.{secrets.token_hex(4)}.tmp")
        _ = staged.write_bytes(gzip.compress(payload.encode(), compresslevel=1))
        _ = staged.replace(path)
        if is_new:
            self._append(profile)
            if secrets.randbelow(_CLEANUP_ONE_IN) == 0:
                self.remove_expired()
        return True

    def purge(self) -> None:
        """Remove every stored profile, the index with them."""
        if self._folder.exists():
            shutil.rmtree(self._folder)

    def remove_expired(self) -> None:
        """Delete every profile older than the lifetime, from where the last sweep stopped."""
        index = self._folder / _INDEX
        if not index.is_file():
            return
        marker = self._folder / _OFFSET
        offset = int(marker.read_text() or 0) if marker.is_file() else 0
        oldest = self._now() - int(self._lifetime.total_seconds())
        with index.open("rb") as handle:
            _ = handle.seek(offset)
            for raw in iter(handle.readline, b""):
                entry = _parse(raw.decode(errors="replace"))
                if entry is not None and entry.time >= oldest:
                    break
                if entry is not None:
                    self._file_of(entry.token).unlink(missing_ok=True)
                offset = handle.tell()
        _ = marker.write_text(str(offset))

    def _append(self, profile: Profile) -> None:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(
            [
                _single_line(profile.token),
                _single_line(profile.ip),
                _single_line(profile.method),
                _single_line(profile.url),
                profile.time,
                "",
                profile.status_code,
                _single_line(profile.virtual_type),
                int(profile.has_errors),
            ]
        )
        descriptor = os.open(self._folder / _INDEX, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            _ = os.write(descriptor, buffer.getvalue().encode())
        finally:
            os.close(descriptor)

    def _path(self, token: str) -> Path:
        if not _TOKEN.fullmatch(token):
            raise InvalidTokenError(token)
        return self._file_of(token)

    def _file_of(self, token: str) -> Path:
        return self._folder / token[-2:] / token[-4:-2] / f"{token}{_SUFFIX}"

    def _now(self) -> int:
        return int(self._clock.now().timestamp())

    @override
    def __repr__(self) -> str:
        """Return where the profiles are kept."""
        return f"{type(self).__name__}({str(self._folder)!r})"


def _single_line(value: str) -> str:
    """Keep a field on one line, so the index can be read backwards line by line."""
    return value.replace("\r", " ").replace("\n", " ")


def _lines_backwards(path: Path) -> Iterator[str]:
    """Yield the lines of ``path`` from the last to the first, reading it in chunks."""
    with path.open("rb") as handle:
        position = handle.seek(0, os.SEEK_END)
        pending = b""
        while position > 0:
            size = min(_CHUNK, position)
            position -= size
            _ = handle.seek(position)
            lines = (handle.read(size) + pending).split(b"\n")
            pending = lines[0]
            for line in reversed(lines[1:]):
                if line:
                    yield line.decode(errors="replace")
        if pending:
            yield pending.decode(errors="replace")


def _parse(line: str) -> ProfileSummary | None:
    rows = list(csv.reader([line]))
    row: list[str] = rows[0] if rows else []
    if len(row) != _FIELDS:
        return None
    token, ip, method, url, time, _parent, status_code, virtual_type, has_errors = row
    try:
        return ProfileSummary(
            token=token,
            ip=ip,
            method=method,
            url=url,
            time=int(time),
            status_code=int(status_code or 0),
            virtual_type=virtual_type or "request",
            has_errors=has_errors == "1",
        )
    except ValueError:
        return None


def _matches(  # noqa: PLR0913 — one keyword per filter, as in find
    entry: ProfileSummary,
    *,
    ip: str | None,
    url: str | None,
    method: str | None,
    start: int | None,
    end: int | None,
    status_code: int | None,
) -> bool:
    if ip and ip not in entry.ip:
        return False
    if url:
        excluded = url.startswith("!")
        if excluded == (url.removeprefix("!") in entry.url):
            return False
    if method and method.upper() not in entry.method.upper():
        return False
    if start is not None and entry.time < start:
        return False
    if end is not None and entry.time > end:
        return False
    return status_code is None or entry.status_code == status_code
