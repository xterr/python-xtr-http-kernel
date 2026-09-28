"""Serving a FastAPI application from a kernel: the one public setup call.

``setup(app, kernel)`` is everything an application calls. It wraps the
application's lifespan so every application life builds, boots and shuts
down its own kernel, and adds one middleware so every request runs inside
the scope its scoped services live in. Call it before the first request —
after the routes and the application's other middleware is fine. An
application that already started refuses new middleware; the framework's
own error surfaces then.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast

from xtr_dependency_injection.integration.fastapi import attach, detach, request_scope
from xtr_dependency_injection.testing import apply_overrides

from ._kernel_middleware import KernelMiddleware
from ._state import OVERRIDES_KEY, STACK_KEY
from .middleware_stack import MiddlewareStack

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Hashable, Mapping

    from fastapi import FastAPI
    from starlette.types import Lifespan
    from xtr_dependency_injection import Kernel
    from xtr_dependency_injection.kernel.compiled_kernel import CompiledKernel

__all__ = ["setup"]


def setup(app: FastAPI, kernel: Kernel) -> None:
    """Serve ``app`` from ``kernel``.

    Nothing is built here: every start of the application's lifespan builds
    the kernel afresh — a built container boots exactly once, and a test
    starts the application many times — applies the overrides
    :func:`xtr_http_kernel.testing.override_services` parked on the
    application, boots, and attaches the kernel so the injection markers
    resolve. The application's own lifespan runs inside, its state passing
    through untouched. On the way out the kernel is detached and shut down.

    Each life also fetches the :class:`~xtr_http_kernel.middleware_stack.MiddlewareStack`
    the kernel's bundles contributed — ordered when the kernel was built,
    highest tag ``priority`` outermost — as the chain every request runs
    through, inside the one middleware this call adds, so the whole chain
    sees the request's scope. A kernel without the http_kernel bundle
    serves with an empty stack.

    Args:
        app: The application to serve, its routes and middleware already
            registered.
        kernel: The recipe to build each application life from.
    """
    app.router.lifespan_context = _serving_lifespan(app, kernel, app.router.lifespan_context)
    app.add_middleware(KernelMiddleware, open_scope=request_scope)


def _serving_lifespan(app: FastAPI, kernel: Kernel, inner: Lifespan[FastAPI]) -> Lifespan[FastAPI]:
    """Return ``inner`` wrapped in one kernel life per application life."""

    @asynccontextmanager
    async def serving(target: FastAPI) -> AsyncGenerator[Mapping[str, object] | None, None]:
        compiled = kernel.build()
        overrides = cast(
            "Mapping[type | tuple[type, Hashable], object] | None",
            getattr(app.state, OVERRIDES_KEY, None),
        )
        if overrides is not None:
            apply_overrides(compiled, overrides)
        async with compiled.lifespan(app):
            attach(app, compiled)
            try:
                setattr(app.state, STACK_KEY, await _stack(compiled))
                async with inner(target) as state:
                    yield state
            finally:
                if hasattr(app.state, STACK_KEY):
                    delattr(app.state, STACK_KEY)
                detach(app)

    # The wrapper yields whatever the application's own lifespan yields;
    # the framework's lifespan type is a union of the two shapes, not a
    # context manager of the union.
    return cast("Lifespan[FastAPI]", serving)


async def _stack(compiled: CompiledKernel) -> MiddlewareStack:
    """Return the kernel's middleware stack, empty when none was registered."""
    container = compiled.container
    if container.has(MiddlewareStack):
        return await container.get(MiddlewareStack)
    return MiddlewareStack()
