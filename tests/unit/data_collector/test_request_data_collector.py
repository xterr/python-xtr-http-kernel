from __future__ import annotations

from typing import cast

from xtr_http_message import ServerRequest

from tests.support.profiling import profiled
from xtr_http_kernel.data_collector import ProfiledRequest
from xtr_http_kernel.data_collector._masking import MASK
from xtr_http_kernel.data_collector.request_data_collector import RequestDataCollector


def test_the_heads_and_parameters_are_kept() -> None:
    data = RequestDataCollector().collect(
        profiled(
            headers={"Accept": "text/html"},
            response_headers={"content-type": "text/html"},
            state={"request_id": "abc", "_profiler.start": 1.0, "user": "ana"},
        )
    )

    assert data["method"] == "GET"
    assert data["path"] == "/books"
    assert data["query"] == {"q": "dune"}
    assert data["request_headers"] == {"Host": "shop.test", "Accept": "text/html"}
    assert data["content_type"] == "text/html"
    assert data["request_id"] == "abc"
    assert list(cast("dict[str, object]", data["state"])) == ["request_id", "user"]
    assert data["body"] is None


def test_credentials_are_masked() -> None:
    data = RequestDataCollector().collect(
        profiled(
            uri="http://shop.test/login?password=hunter2&next=/",
            headers={"Authorization": "Bearer x", "Cookie": "sid=1"},
            response_headers={"set-cookie": "sid=2"},
        )
    )

    assert data["request_headers"] == {"Host": "shop.test", "Authorization": MASK, "Cookie": MASK}
    assert data["response_headers"] == {"set-cookie": MASK}
    assert data["query"] == {"password": MASK, "next": "/"}


def test_a_parsed_body_is_kept_masked_and_another_value_cloned() -> None:
    request = ServerRequest("POST", "http://shop.test/login").with_parsed_body(
        {"user": "ana", "password": "x", "tags": ["a"]}
    )

    data = RequestDataCollector().collect(ProfiledRequest(request, 200, {}, {}))

    body = cast("dict[str, object]", data["body"])
    assert body["user"] == "ana"
    assert body["password"] == MASK
    assert cast("dict[str, object]", body["tags"])["kind"] == "sequence"


def test_a_body_that_is_no_mapping_is_cloned() -> None:
    request = ServerRequest("POST", "http://shop.test/").with_parsed_body(["a"])

    data = RequestDataCollector().collect(ProfiledRequest(request, 200, {}, {}))

    assert cast("dict[str, object]", data["body"])["kind"] == "sequence"


def test_once_sent_a_curl_command_replays_the_request_masked() -> None:
    collector = RequestDataCollector()
    request = profiled("POST", headers={"Authorization": "Bearer x"})

    data = collector.late_collect(collector.collect(request), request)

    assert data["curl_command"] == (
        "curl -X POST 'http://shop.test/books?q=dune' -H 'Host: shop.test' "
        "-H 'Authorization: ******'"
    )
    assert collector.name == "request"
