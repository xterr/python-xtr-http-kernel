"""Mounting a compiled kernel's route table on an application."""

from __future__ import annotations

from fastapi import FastAPI
from xtr_dependency_injection import Kernel

from xtr_http_kernel._route_mount import mount_routes
from xtr_http_kernel.bundle import HttpKernelBundle


def test_a_kernel_without_the_http_kernel_bundle_mounts_nothing() -> None:
    app = FastAPI()
    before = len(app.routes)

    mounted = mount_routes(app, Kernel("xtr_http_kernel.bundle", env="test", bundles={}).build())

    assert mounted is None
    assert len(app.routes) == before


def test_the_mounted_table_is_returned_and_reached_by_name() -> None:
    app = FastAPI()
    kernel = Kernel(
        "xtr_http_kernel.bundle",
        env="test",
        bundles={HttpKernelBundle: {"all": True}},
        resources=("tests.fixtures.routing.loaders",),
    )

    mounted = mount_routes(app, kernel.build())

    assert mounted is not None
    assert app.url_path_for("books_show", book_id="7") == "/books/7"


def test_an_empty_table_adds_no_router() -> None:
    app = FastAPI()
    before = len(app.routes)
    kernel = Kernel("xtr_http_kernel.bundle", env="test", bundles={HttpKernelBundle: {"all": True}})

    mounted = mount_routes(app, kernel.build())

    assert mounted is not None
    assert len(app.routes) == before
