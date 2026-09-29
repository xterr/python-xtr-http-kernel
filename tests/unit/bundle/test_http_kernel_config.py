"""Unit tests for :class:`xtr_http_kernel.bundle.HttpKernelConfig`."""

from __future__ import annotations

import pytest

from xtr_http_kernel.bundle import HttpKernelConfig
from xtr_http_kernel.exception import HttpKernelError, InvalidArgumentError


def test_it_builds_with_no_arguments() -> None:
    config = HttpKernelConfig()

    assert config.request_id_header == "X-Request-Id"
    assert config.trust_request_id is True
    assert config.disallow_search_indexing is False
    assert config.log_channel == "request"
    assert config.middleware_priority == 0
    assert config.app is None


def test_it_accepts_a_custom_header_and_channel() -> None:
    config = HttpKernelConfig(request_id_header="X-Trace-Id", log_channel="http")

    assert config.request_id_header == "X-Trace-Id"
    assert config.log_channel == "http"


def test_it_refuses_an_empty_request_id_header() -> None:
    with pytest.raises(InvalidArgumentError, match="request_id_header"):
        _ = HttpKernelConfig(request_id_header="")


@pytest.mark.parametrize("header", ["X Request Id", "X-Request-Id:", "naïve", "a\tb"])
def test_it_refuses_a_header_that_is_not_a_token(header: str) -> None:
    with pytest.raises(InvalidArgumentError, match="request_id_header"):
        _ = HttpKernelConfig(request_id_header=header)


def test_it_refuses_an_empty_log_channel() -> None:
    with pytest.raises(InvalidArgumentError, match="log_channel"):
        _ = HttpKernelConfig(log_channel="")


def test_it_accepts_an_app_import_string() -> None:
    config = HttpKernelConfig(app="shop.web:app")

    assert config.app == "shop.web:app"


@pytest.mark.parametrize("app", ["shop.web", "shop:web:app", ":app", "shop.web:"])
def test_it_refuses_an_app_string_without_one_module_and_one_attribute(app: str) -> None:
    with pytest.raises(InvalidArgumentError, match="app"):
        _ = HttpKernelConfig(app=app)


def test_a_refused_value_is_an_http_kernel_error_and_a_value_error() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = HttpKernelConfig(log_channel="")

    assert isinstance(raised.value, HttpKernelError)
    assert isinstance(raised.value, ValueError)
