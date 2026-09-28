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
from tests.support.bundles import ServedBundle
from xtr_http_kernel import setup
from xtr_http_kernel.testing import override_services

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from xtr_dependency_injection.kernel.compiled_kernel import CompiledKernel

pytestmark = pytest.mark.anyio

_FACTORIES_KEY = "_xtr_http_kernel_middleware"


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


async def test_the_contributed_factories_wait_on_the_state_sorted_outermost_first() -> None:
    app = FastAPI()
    setup(app, _kernel())

    async with app.router.lifespan_context(app):
        factories = cast("tuple[object, ...]", getattr(app.state, _FACTORIES_KEY))
        labels = [cast("str", getattr(factory, "label", "")) for factory in factories]

    assert labels == ["outer", "plain", "inner"]
    assert getattr(app.state, _FACTORIES_KEY, None) is None
