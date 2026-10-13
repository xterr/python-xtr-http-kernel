"""The error a response that already is a message fails conversion with."""

from __future__ import annotations

from xtr_http_kernel import HttpKernelError, ResponseAlreadyAMessageError


def test_it_derives_from_the_package_base_error() -> None:
    error = ResponseAlreadyAMessageError("Response")

    assert isinstance(error, HttpKernelError)


def test_it_carries_the_kind_of_response_as_an_attribute() -> None:
    error = ResponseAlreadyAMessageError("Response")

    assert error.response == "Response"


def test_the_message_names_the_response_and_how_to_read_its_body() -> None:
    error = ResponseAlreadyAMessageError("Response")

    assert str(error) == (
        'The response "Response" already is a message; use it as one '
        '(read its body with "await response.get_body().get_contents()") '
        "instead of converting it."
    )
