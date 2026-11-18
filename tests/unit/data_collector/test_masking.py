from __future__ import annotations

import pytest

from xtr_http_kernel.data_collector._masking import (
    MASK,
    is_sensitive_field,
    is_sensitive_header,
    masked_field,
    masked_header,
)


@pytest.mark.parametrize("name", ["Authorization", "cookie", "Set-Cookie", "X-Api-Key"])
def test_a_credential_header_is_masked(name: str) -> None:
    assert is_sensitive_header(name)
    assert masked_header(name, "value") == MASK


@pytest.mark.parametrize("name", ["password", "new_password", "client_secret", "csrf_token"])
def test_a_credential_field_is_masked(name: str) -> None:
    assert is_sensitive_field(name)
    assert masked_field(name, "value") == MASK


def test_anything_else_is_kept() -> None:
    assert masked_header("Accept", "text/html") == "text/html"
    assert masked_field("next", "/") == "/"
