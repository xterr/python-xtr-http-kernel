from __future__ import annotations

import pytest

from xtr_http_kernel.exception import UnknownCollectorError
from xtr_http_kernel.profiler import Profile


def _profile() -> Profile:
    return Profile(
        "a1b2c3",
        ip="127.0.0.1",
        method="GET",
        url="http://shop.test/books",
        time=1_700_000_000,
        status_code=200,
        collectors={"request": {"method": "GET"}},
    )


def test_a_profile_keeps_each_collectors_data_by_name() -> None:
    profile = _profile()

    profile.add_collector("time", {"duration_ms": 3.5})

    assert profile.has_collector("time")
    assert profile.get_collector("time") == {"duration_ms": 3.5}


def test_asking_for_a_collector_it_does_not_hold_names_the_ones_it_does() -> None:
    with pytest.raises(
        UnknownCollectorError, match=r'"router" does not exist.*"request"'
    ) as caught:
        _ = _profile().get_collector("router")

    assert caught.value.available == ("request",)


def test_a_profile_round_trips_through_plain_data() -> None:
    profile = _profile()

    restored = Profile.from_dict(profile.to_dict())

    assert restored.to_dict() == profile.to_dict()


def test_fields_of_the_wrong_type_read_as_their_defaults() -> None:
    restored = Profile.from_dict(
        {"token": "abc", "time": "soon", "status_code": True, "collectors": {"x": 1}}
    )

    assert restored.time == 0
    assert restored.status_code == 0
    assert restored.virtual_type == "request"
    assert restored.collectors == {}


def test_a_profile_shows_its_head() -> None:
    assert repr(_profile()) == "Profile('a1b2c3', GET http://shop.test/books, status=200)"
