"""The setup call: a kernel behind the application's lifespan, one middleware in front."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast

import pytest
from fastapi import FastAPI
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.exception import FastapiIntegrationError
from xtr_dependency_injection.integration.fastapi import provider, request_scope

from tests.fixtures.served_app.services import Greeter
from tests.support.bundles import PlainStamp, ServedBundle, Stamp
from tests.support.serving import serving
from xtr_http_kernel import MiddlewareStack, setup
from xtr_http_kernel.bundle import HttpKernelBundle
from xtr_http_kernel.testing import override_services

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from xtr_dependency_injection.kernel.compiled_kernel import CompiledKernel

pytestmark = pytest.mark.anyio

_STACK_KEY = "_xtr_http_kernel_middleware"


def _kernel() -> Kernel:
    return Kernel(
        "tests.fixtures.served_app",
        env="test",
        bundles={ServedBundle: {"all": True}},
    )


@pytest.fixture
def builds(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Journal every ``Kernel.build`` call for the span of one test."""
    journal: list[str] = []
    original = Kernel.build

    def counting_build(kernel: Kernel) -> CompiledKernel:
        journal.append("build")
        return original(kernel)

    monkeypatch.setattr(Kernel, "build", counting_build)
    return journal


def test_setup_builds_nothing_at_call_time(builds: list[str]) -> None:
    app = FastAPI()

    setup(app, _kernel())

    assert builds == []


def test_setup_adds_exactly_one_middleware() -> None:
    app = FastAPI()

    setup(app, _kernel())

    names = [cast("type[object]", middleware.cls).__name__ for middleware in app.user_middleware]
    assert names == ["KernelMiddleware"]


async def test_every_application_life_builds_a_fresh_kernel(builds: list[str]) -> None:
    app = FastAPI()
    setup(app, _kernel())

    async with app.router.lifespan_context(app):
        pass
    async with app.router.lifespan_context(app):
        pass

    assert builds == ["build", "build"]


async def test_the_kernel_serves_the_application_only_while_it_lives() -> None:
    app = FastAPI()
    setup(app, _kernel())

    async with app.router.lifespan_context(app), request_scope(app):
        pass

    with pytest.raises(FastapiIntegrationError, match="no kernel serves this application"):
        async with request_scope(app):
            pytest.fail("the scope must not open once the application life ended")


async def test_pending_overrides_apply_at_the_next_build() -> None:
    app = FastAPI()
    setup(app, _kernel())
    resolve = provider("service", Greeter, None)

    class Fake:
        def greet(self, name: str) -> str:
            return f"faked {name}"

    with override_services(app, {Greeter: Fake()}):
        async with app.router.lifespan_context(app), request_scope(app):
            overridden = await resolve()

    async with app.router.lifespan_context(app), request_scope(app):
        real = await resolve()

    assert isinstance(overridden, Fake)
    assert isinstance(real, Greeter)


async def test_the_applications_own_lifespan_state_passes_through() -> None:
    @asynccontextmanager
    async def app_lifespan(_app: FastAPI) -> AsyncGenerator[dict[str, str], None]:
        yield {"marker": "from-the-app"}

    app = FastAPI(lifespan=app_lifespan)
    setup(app, _kernel())

    async with app.router.lifespan_context(app) as state:
        assert state == {"marker": "from-the-app"}


async def test_the_kernels_stack_waits_on_the_state_sorted_outermost_first() -> None:
    app = FastAPI()
    setup(
        app,
        Kernel(
            "tests.fixtures.served_app",
            env="test",
            bundles={ServedBundle: {"all": True}, HttpKernelBundle: {"all": True}},
        ),
    )

    async with app.router.lifespan_context(app):
        stack = cast("MiddlewareStack", getattr(app.state, _STACK_KEY))
        labels = [factory.label for factory in stack if isinstance(factory, (Stamp, PlainStamp))]

    assert labels == ["outer", "plain", "inner"]
    assert getattr(app.state, _STACK_KEY, None) is None


async def test_without_the_bundle_requests_run_with_an_empty_stack() -> None:
    app = FastAPI()

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"ping": "pong"}

    # The kernel's report still lists ServedBundle's tagged stamps; only the
    # http_kernel bundle turns them into a stack, so none of them runs.
    setup(app, _kernel())

    async with serving(app) as client:
        stack = cast("MiddlewareStack", getattr(app.state, _STACK_KEY))
        assert isinstance(stack, MiddlewareStack)
        assert len(stack) == 0
        response = await client.get("/ping")

    assert response.status_code == 200
    assert getattr(app.state, _STACK_KEY, None) is None
