"""Serving a FastAPI application from a kernel: the one public setup call.

``setup(app, kernel)`` is everything an application calls. It compiles the
kernel once to mount the routes the application's routes files register,
wraps the application's lifespan so every application life boots and shuts
down its own kernel, and adds one middleware so every request runs inside
the scope its scoped services live in. Call it after the application's own
routes and before the first request. An application that already started refuses new
middleware; the framework's own error surfaces then.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from xtr_dependency_injection.integration.fastapi import attach, detach, request_scope
from xtr_dependency_injection.testing import apply_overrides

from ._kernel_middleware import KernelMiddleware
from ._staging import mount_routes
from ._state import OVERRIDES_KEY, STACK_KEY
from .middleware_stack import MiddlewareStack
from .routing.route_registry import ROUTE_REGISTRY_PARAMETER, RouteRegistry

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Hashable, Mapping

    from fastapi import FastAPI
    from starlette.types import Lifespan
    from xtr_dependency_injection import Kernel
    from xtr_dependency_injection.kernel.compiled_kernel import CompiledKernel

__all__ = ["setup"]


def setup(app: FastAPI, kernel: Kernel) -> None:
    """Serve ``app`` from ``kernel``.

    The kernel is compiled here, once — nothing is booted and no service is
    built — and the routes the application's routes files register are added
    to ``app``. Routing is never imported automatically: a resource no routes
    file includes is staged and dropped. From here on the application holds
    every route it serves, so whatever reads its routes — the router
    commands, the API description, ``url_path_for`` — sees them all without
    starting it. A mounted route colliding with one the application declared
    itself is refused here, and so is a routes file naming a resource nothing
    installed contributes. Configuration and the environment are therefore
    read when this runs.

    The first start of the application's lifespan boots that compiled kernel;
    every later start builds the kernel afresh — a built container boots
    exactly once, and a test starts the application many times. Each start
    applies the overrides :func:`xtr_http_kernel.testing.override_services`
    parked on the application, boots, and attaches the kernel so the injection
    markers resolve. The application's own lifespan runs inside, its state
    passing through untouched. On the way out the kernel is detached and shut
    down.

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

    Raises:
        RouteConflictError: A contributed route shares a name, or a method at
            the same path, with one the application declared itself.
        InvalidArgumentError: Two routes of one resource claim a name, or a
            routes file includes a resource nothing installed contributes.
    """
    first = kernel.build()
    _mount(app, first)
    builds = _Builds(kernel, [first])
    app.router.lifespan_context = _serving_lifespan(app, builds, app.router.lifespan_context)
    app.add_middleware(KernelMiddleware, open_scope=request_scope)


def _mount(app: FastAPI, compiled: CompiledKernel) -> None:
    """Mount the routes the kernel's registry holds, as the routes files include them.

    A kernel without the http_kernel bundle has no registry, and an
    application whose routes files include nothing serves only its own
    routes: routing is never imported automatically.
    """
    container = compiled.container
    if not container.has_parameter(ROUTE_REGISTRY_PARAMETER):
        return
    registry = container.get_parameter(ROUTE_REGISTRY_PARAMETER)
    if isinstance(registry, RouteRegistry):
        mount_routes(app, registry)


@dataclass(slots=True)
class _Builds:
    """Hands each application life a compiled kernel: the one setup built, then fresh ones.

    The routes were mounted once, in ``setup``; no later build changes what
    the application serves. A fresh build compiles the registry again, and
    each life boots its own container against the one mounted application.
    """

    kernel: Kernel
    unused: list[CompiledKernel] = field(default_factory=list)

    def next(self) -> CompiledKernel:
        if self.unused:
            return self.unused.pop()
        return self.kernel.build()


def _serving_lifespan(app: FastAPI, builds: _Builds, inner: Lifespan[FastAPI]) -> Lifespan[FastAPI]:
    """Return ``inner`` wrapped in one kernel life per application life."""

    @asynccontextmanager
    async def serving(target: FastAPI) -> AsyncGenerator[Mapping[str, object] | None, None]:
        compiled = builds.next()
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
