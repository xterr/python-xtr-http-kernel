"""The factory the served application's responses come from."""

from __future__ import annotations

from xtr_http_message_contracts.factory import ResponseFactoryInterface

from xtr_http_kernel.bridge import Response, ResponseFactory


def test_the_factory_is_a_response_factory() -> None:
    assert ResponseFactoryInterface in ResponseFactory.__mro__


def test_a_response_with_nothing_asked_for_is_the_usual_one() -> None:
    response = ResponseFactory().create_response()

    assert (response.get_status_code(), response.get_reason_phrase()) == (200, "OK")


def test_a_response_is_one_an_endpoint_can_return_as_it_is() -> None:
    assert isinstance(ResponseFactory().create_response(), Response)


def test_a_status_with_no_phrase_asked_for_takes_the_recommended_one() -> None:
    assert ResponseFactory().create_response(404).get_reason_phrase() == "Not Found"


def test_asking_for_no_phrase_is_not_the_same_as_asking_for_nothing() -> None:
    assert ResponseFactory().create_response(404, "").get_reason_phrase() == ""


def test_a_phrase_given_is_the_phrase_carried() -> None:
    assert ResponseFactory().create_response(404, "Nowhere").get_reason_phrase() == "Nowhere"


def test_a_status_with_no_recommended_phrase_carries_none() -> None:
    assert ResponseFactory().create_response(599).get_reason_phrase() == ""


def test_a_response_starts_with_no_header_and_no_body() -> None:
    response = ResponseFactory().create_response()

    assert (dict(response.get_headers()), bytes(response.get_body())) == ({}, b"")
