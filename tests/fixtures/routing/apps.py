"""An entry point as an application writes it: its own route, then ``setup()``."""

from __future__ import annotations

from fastapi import FastAPI
from xtr_dependency_injection import Kernel

from xtr_http_kernel import setup
from xtr_http_kernel.bundle import HttpKernelBundle

app = FastAPI()


@app.get("/own", name="own")
async def own() -> dict[str, str]:
    return {}


setup(
    app,
    Kernel(
        "tests.fixtures.routing",
        env="test",
        bundles={HttpKernelBundle: {"all": True}},
        resources=("tests.fixtures.routing.loaders",),
    ),
)
