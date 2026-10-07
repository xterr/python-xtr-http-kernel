"""What the package root re-exports, so an application imports from one place."""

from __future__ import annotations

import xtr_http_kernel
from xtr_http_kernel import exception as exception_package


def test_the_root_exports_every_error_the_library_raises() -> None:
    assert set(exception_package.__all__) <= set(xtr_http_kernel.__all__)


def test_each_error_at_the_root_is_the_one_the_exception_package_declares() -> None:
    for name in exception_package.__all__:
        assert getattr(xtr_http_kernel, name) is getattr(exception_package, name)
