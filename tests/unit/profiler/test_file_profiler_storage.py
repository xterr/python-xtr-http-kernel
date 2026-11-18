from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from xtr_clock import MockClock

from xtr_http_kernel.exception import InvalidTokenError
from xtr_http_kernel.profiler import FileProfilerStorage, Profile

if TYPE_CHECKING:
    from pathlib import Path

_START = 1_767_225_600  # 2026-01-01 00:00:00 UTC


@dataclass(frozen=True)
class _Search:
    ip: str | None = None
    url: str | None = None
    method: str | None = None
    start: int | None = None
    end: int | None = None
    status_code: int | None = None


@pytest.fixture
def clock() -> MockClock:
    return MockClock("2026-01-01 00:00:00")


@pytest.fixture
def storage(tmp_path: Path, clock: MockClock) -> FileProfilerStorage:
    return FileProfilerStorage(tmp_path / "profiler", timedelta(days=2), clock)


def _profile(  # noqa: PLR0913 — one keyword per field a test varies
    token: str,
    *,
    time: int = _START,
    ip: str = "127.0.0.1",
    method: str = "GET",
    url: str = "http://shop.test/books",
    status_code: int = 200,
) -> Profile:
    return Profile(
        token,
        ip=ip,
        method=method,
        url=url,
        time=time,
        status_code=status_code,
        collectors={"request": {"method": method}},
    )


def test_a_profile_is_stored_under_its_last_token_characters(
    storage: FileProfilerStorage,
) -> None:
    assert storage.write(_profile("a1b2c3"))

    assert (storage.folder / "c3" / "b2" / "a1b2c3.json.gz").is_file()


def test_a_written_profile_reads_back_the_same(storage: FileProfilerStorage) -> None:
    profile = _profile("a1b2c3")
    _ = storage.write(profile)

    restored = storage.read("a1b2c3")

    assert restored is not None
    assert restored.to_dict() == profile.to_dict()


def test_an_unknown_token_reads_as_nothing(storage: FileProfilerStorage) -> None:
    assert storage.read("ffffff") is None


@pytest.mark.parametrize("token", ["../etc", "a/b", "", "a b", "a.b"])
def test_a_token_that_is_not_one_is_refused_before_any_path_is_built(
    storage: FileProfilerStorage, token: str
) -> None:
    with pytest.raises(InvalidTokenError):
        _ = storage.read(token)


def test_rewriting_a_profile_does_not_list_it_twice(storage: FileProfilerStorage) -> None:
    _ = storage.write(_profile("a1b2c3"))
    _ = storage.write(_profile("a1b2c3", status_code=500))

    found = storage.find(None, None, 10, None)

    assert [entry.token for entry in found] == ["a1b2c3"]
    restored = storage.read("a1b2c3")
    assert restored is not None
    assert restored.status_code == 500


def test_a_search_lists_the_newest_first_up_to_the_limit(
    storage: FileProfilerStorage,
) -> None:
    for offset, token in enumerate(["aaaa01", "aaaa02", "aaaa03"]):
        _ = storage.write(_profile(token, time=_START + offset))

    found = storage.find(None, None, 2, None)

    assert [entry.token for entry in found] == ["aaaa03", "aaaa02"]


def test_a_search_reads_an_index_longer_than_one_chunk(storage: FileProfilerStorage) -> None:
    tokens = [f"t{number:05d}" for number in range(100)]
    for token in tokens:
        _ = storage.write(_profile(token, url=f"http://shop.test/{'x' * 40}/{token}"))

    found = storage.find(None, None, 1000, None)

    assert [entry.token for entry in found] == list(reversed(tokens))


@pytest.mark.parametrize(
    ("search", "expected"),
    [
        (_Search(ip="10.0"), ["bbbb02"]),
        (_Search(url="/admin"), ["bbbb03"]),
        (_Search(url="!/admin"), ["bbbb02", "bbbb01"]),
        (_Search(method="post"), ["bbbb02"]),
        (_Search(status_code=404), ["bbbb03"]),
        (_Search(start=_START + 1), ["bbbb03", "bbbb02"]),
        (_Search(end=_START + 1), ["bbbb02", "bbbb01"]),
    ],
)
def test_a_search_applies_every_filter(
    storage: FileProfilerStorage, search: _Search, expected: list[str]
) -> None:
    _ = storage.write(_profile("bbbb01"))
    _ = storage.write(_profile("bbbb02", time=_START + 1, ip="10.0.0.2", method="POST"))
    _ = storage.write(
        _profile("bbbb03", time=_START + 2, url="http://shop.test/admin", status_code=404)
    )

    found = storage.find(
        search.ip,
        search.url,
        10,
        search.method,
        start=search.start,
        end=search.end,
        status_code=search.status_code,
    )

    assert [entry.token for entry in found] == expected


def test_a_search_asks_the_filter_last(storage: FileProfilerStorage) -> None:
    _ = storage.write(_profile("cccc01"))
    _ = storage.write(_profile("cccc02", status_code=418))

    found = storage.find(None, None, 10, None, filter=lambda entry: entry.status_code != 418)

    assert [entry.token for entry in found] == ["cccc01"]


def test_a_search_of_an_empty_store_finds_nothing(storage: FileProfilerStorage) -> None:
    assert storage.find(None, None, 10, None) == []
    _ = storage.write(_profile("dddd01"))
    assert storage.find(None, None, 0, None) == []


def test_a_search_leaves_out_profiles_past_their_lifetime(
    storage: FileProfilerStorage, clock: MockClock
) -> None:
    _ = storage.write(_profile("eeee01"))
    clock.sleep(timedelta(days=3).total_seconds())
    _ = storage.write(_profile("eeee02", time=_START + int(timedelta(days=3).total_seconds())))

    found = storage.find(None, None, 10, None)

    assert [entry.token for entry in found] == ["eeee02"]


def test_removing_expired_profiles_deletes_only_those_and_remembers_where_it_stopped(
    storage: FileProfilerStorage, clock: MockClock
) -> None:
    _ = storage.write(_profile("ffff01"))
    clock.sleep(timedelta(days=3).total_seconds())
    later = _START + int(timedelta(days=3).total_seconds())
    _ = storage.write(_profile("ffff02", time=later))

    storage.remove_expired()

    assert storage.read("ffff01") is None
    assert storage.read("ffff02") is not None
    offset = int((storage.folder / "index.csv.offset").read_text())
    assert offset > 0
    storage.remove_expired()
    assert int((storage.folder / "index.csv.offset").read_text()) == offset


def test_removing_expired_profiles_from_an_empty_store_does_nothing(
    storage: FileProfilerStorage,
) -> None:
    storage.remove_expired()

    assert not storage.folder.exists()


def test_a_line_the_index_cannot_read_is_skipped(storage: FileProfilerStorage) -> None:
    _ = storage.write(_profile("gggg01"))
    with (storage.folder / "index.csv").open("a") as index:
        _ = index.write("broken\nx,y,z,w,notatime,,200,request,0\n")

    found = storage.find(None, None, 10, None)

    assert [entry.token for entry in found] == ["gggg01"]


def test_a_url_spanning_lines_stays_on_one_index_line(storage: FileProfilerStorage) -> None:
    _ = storage.write(_profile("hhhh01", url="http://shop.test/a\nb"))

    (entry,) = storage.find(None, None, 10, None)

    assert entry.url == "http://shop.test/a b"


def test_purging_removes_everything(storage: FileProfilerStorage) -> None:
    _ = storage.write(_profile("iiii01"))

    storage.purge()
    storage.purge()

    assert storage.find(None, None, 10, None) == []
    assert storage.read("iiii01") is None


def test_concurrent_writes_each_add_one_whole_index_line(storage: FileProfilerStorage) -> None:
    tokens = [f"j{number:05d}" for number in range(50)]

    def write(token: str) -> bool:
        return storage.write(_profile(token))

    with ThreadPoolExecutor(max_workers=8) as pool:
        _ = list(pool.map(write, tokens))

    found = storage.find(None, None, 100, None)
    assert sorted(entry.token for entry in found) == tokens


def test_a_storage_shows_its_folder(storage: FileProfilerStorage) -> None:
    assert repr(storage) == f"FileProfilerStorage({str(storage.folder)!r})"


def test_a_storage_without_a_clock_reads_the_system_one(tmp_path: Path) -> None:
    storage = FileProfilerStorage(tmp_path)

    _ = storage.write(_profile("kkkk01", time=int(MockClock().now().timestamp())))

    assert [entry.token for entry in storage.find(None, None, 10, None)] == ["kkkk01"]
