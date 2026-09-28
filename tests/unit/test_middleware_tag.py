"""The tag a bundle puts on the middleware factories it contributes."""

from __future__ import annotations

from xtr_http_kernel import MIDDLEWARE_TAG


def test_the_tag_is_the_name_bundles_and_setup_agree_on() -> None:
    assert MIDDLEWARE_TAG == "http_kernel.middleware"
