"""The contract tests of the fakes the other tests build on.

A fake that drifts from what it stands in for turns every test that uses it
into a test of nothing, so each one is held to the promise its name makes.
"""

from __future__ import annotations

from tests.support.short_read_file import ShortReadFile


def test_the_short_read_file_answers_with_less_than_was_asked_for() -> None:
    with ShortReadFile(b"firstsecond", 5) as file:
        assert file.read(100) == b"first"


def test_the_short_read_file_hands_over_the_whole_of_what_it_holds() -> None:
    with ShortReadFile(b"firstsecond", 5) as file:
        assert [file.read(100) for _ in range(4)] == [b"first", b"secon", b"d", b""]


def test_the_short_read_file_does_not_seek() -> None:
    with ShortReadFile(b"firstsecond", 5) as file:
        assert file.seekable() is False


def test_the_short_read_file_asked_for_everything_answers_in_full() -> None:
    with ShortReadFile(b"firstsecond", 5) as file:
        assert file.read() == b"firstsecond"
