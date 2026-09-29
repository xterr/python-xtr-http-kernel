"""A rate limit on a route, a router or a whole application."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Final, ParamSpec, TypeVar, cast, overload

from fastapi import APIRouter
from fastapi.params import Depends

# The framework reads the dependency's signature at runtime to hand it the request.
from starlette.requests import Request
from xtr_clock import Clock
from xtr_dependency_injection import current_unit_of_work
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_rate_limiter import RateLimiterFactoryInterface, RateLimitExceededEvent

from xtr_http_kernel.exception import (
    InvalidRateLimitError,
    TooManyRequestsError,
    UnknownRateLimiterError,
)

from ._applied_rate_limit import STATE_KEY, AppliedRateLimit, applied_rate_limit

if TYPE_CHECKING:
    from collections.abc import Iterable

    from xtr_service_contracts import ContainerInterface

__all__ = ["RateLimitKey", "RateLimited"]

RateLimitKey = str | Callable[[Request], str | Awaitable[str]]
"""What a request is counted under: a fixed key, or one worked out from the request."""

_P = ParamSpec("_P")
_R = TypeVar("_R")

_HIDDEN_PREFIX: Final = "_xtr_rate_limit_"
"""What the parameter a decorated endpoint gains is called, numbered."""


class RateLimited(Depends):
    """A rate limit a request must pass before its endpoint runs.

    Attributes:
        limiter: The name the limiter is configured under.
        key: What a request is counted under; the client's address, the
            method and the route's path template when ``None``.
        tokens: The tokens one request consumes.
        methods: The methods limited; every method when empty.
        expose_headers: Whether the response reports this limit.

    One declaration, written wherever the framework takes a dependency, or
    as a decorator:

    ```python
    @router.get("/books")
    @RateLimited("api")  # below the route: the route reads what it decorates
    async def list_books() -> list[Book]: ...


    @router.post("/login", dependencies=[RateLimited("login", key=by_username)])
    async def login() -> None: ...


    reports = RateLimited("reports", expose_headers=True)(APIRouter(prefix="/reports"))
    app.include_router(admin, dependencies=[RateLimited("admin")])
    app = FastAPI(dependencies=[RateLimited("global")])
    ```

    The limit runs after routing and before the endpoint, in the order the
    framework resolves dependencies: the application's, the routers', then
    the route's. A request the limiter refuses is answered ``429 Too Many
    Requests`` with ``Retry-After``, and a
    :class:`~xtr_rate_limiter.RateLimitExceededEvent` is dispatched first.
    Limits consulted before a refusal keep their spend.

    With ``expose_headers``, the response carries ``X-RateLimit-Limit``,
    ``X-RateLimit-Remaining`` and ``X-RateLimit-Reset`` for the limit closest
    to refusing among those exposing theirs; a refusing limit always speaks,
    and one that does not expose its state leaves the response without them.
    """

    # Set through object.__setattr__ in __init__: the base is a frozen dataclass.
    limiter: str  # pyright: ignore[reportUninitializedInstanceVariable]
    key: RateLimitKey | None  # pyright: ignore[reportUninitializedInstanceVariable]
    tokens: int  # pyright: ignore[reportUninitializedInstanceVariable]
    methods: frozenset[str]  # pyright: ignore[reportUninitializedInstanceVariable]
    expose_headers: bool  # pyright: ignore[reportUninitializedInstanceVariable]

    def __init__(
        self,
        limiter: str,
        *,
        key: RateLimitKey | None = None,
        tokens: int = 1,
        methods: str | Iterable[str] = (),
        expose_headers: bool = False,
    ) -> None:
        """Limit requests through the configured limiter ``limiter``.

        Args:
            limiter: The name the limiter is configured under.
            key: What the request is counted under — a string, or a
                function of the request returning one, awaited when it
                returns an awaitable. By default the client's address, the
                method and the route's path template — ``/books/{isbn}``,
                so every book shares one count.
            tokens: The tokens one request consumes.
            methods: The methods limited; every method when empty. ``GET``
                also limits ``HEAD``.
            expose_headers: Report this limit in ``X-RateLimit-*`` headers.

        Raises:
            InvalidRateLimitError: When ``tokens`` is below one.
        """
        if tokens < 1:
            raise InvalidRateLimitError(
                f"A rate limit must consume at least one token, got {tokens}.",
            )
        normalized = {methods.upper()} if isinstance(methods, str) else {m.upper() for m in methods}
        if "GET" in normalized:
            normalized.add("HEAD")
        # Every declaration runs on its own: two limits sharing a limiter both count.
        super().__init__(dependency=self._enforce, use_cache=False)
        # The framework's dependency marker is a frozen dataclass.
        object.__setattr__(self, "limiter", limiter)
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "tokens", tokens)
        object.__setattr__(self, "methods", frozenset(normalized))
        object.__setattr__(self, "expose_headers", expose_headers)

    @overload
    def __call__(self, target: APIRouter, /) -> APIRouter: ...

    @overload
    def __call__(self, target: Callable[_P, _R], /) -> Callable[_P, _R]: ...

    def __call__(self, target: APIRouter | Callable[_P, _R], /) -> APIRouter | Callable[_P, _R]:
        """Apply this limit to every route of ``target``, or to the endpoint ``target``.

        A router must have no route yet: the framework copies a router's
        dependencies into each route as the route is added. An endpoint must
        be decorated before the route is declared — below its route
        decorator — since the route reads the endpoint's signature then.

        Raises:
            InvalidRateLimitError: When ``target`` is a router that already
                has routes.
        """
        if isinstance(target, APIRouter):
            if target.routes:
                raise InvalidRateLimitError(
                    "Rate limit a router before adding its routes, or give the limit to "
                    "include_router(..., dependencies=[...]).",
                )
            target.dependencies.append(self)
            return target
        return self._decorate(target)

    def _decorate(self, endpoint: Callable[_P, _R]) -> Callable[_P, _R]:
        """Return ``endpoint`` taking this limit as a hidden dependency.

        The wrapper's signature is the endpoint's with one keyword-only
        parameter more, defaulting to this limit — which the framework reads
        as a dependency, and keeps out of the published schema. The wrapper
        drops it before calling the endpoint.
        """
        signature = inspect.signature(endpoint)
        taken = set(signature.parameters)
        index = 0
        while f"{_HIDDEN_PREFIX}{index}" in taken:
            index += 1
        name = f"{_HIDDEN_PREFIX}{index}"

        parameters = list(signature.parameters.values())
        keywords = [p for p in parameters if p.kind is inspect.Parameter.VAR_KEYWORD]
        others = [p for p in parameters if p.kind is not inspect.Parameter.VAR_KEYWORD]
        hidden = inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, default=self)
        extended = signature.replace(parameters=[*others, hidden, *keywords])

        if inspect.iscoroutinefunction(endpoint):
            call = cast("Callable[_P, Awaitable[object]]", endpoint)

            @functools.wraps(endpoint)
            async def asynchronous(*args: _P.args, **kwargs: _P.kwargs) -> object:
                _ = kwargs.pop(name, None)
                return await call(*args, **kwargs)

            wrapper = cast("Callable[_P, _R]", asynchronous)
        else:

            @functools.wraps(endpoint)
            def synchronous(*args: _P.args, **kwargs: _P.kwargs) -> _R:
                _ = kwargs.pop(name, None)
                return endpoint(*args, **kwargs)

            wrapper = synchronous
        # The framework reads the signature from here; functions take any attribute.
        wrapper.__signature__ = extended  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[unresolved-attribute]
        return wrapper

    async def _enforce(self, request: Request) -> None:
        """Consume this limit for ``request``, refusing it with 429 when the limiter does.

        Raises:
            UnknownRateLimiterError: When no limiter is configured under the
                name, or no kernel serves the request.
            TooManyRequestsError: When the limiter refuses the request.
        """
        if self.methods and request.method not in self.methods:
            return
        container = current_unit_of_work()
        if container is None or not container.has(RateLimiterFactoryInterface, self.limiter):
            raise UnknownRateLimiterError(self.limiter, await _configured(container))

        key = await self._key_of(request)
        factory = await container.get(RateLimiterFactoryInterface, self.limiter)
        rate_limit = await factory.create(key).consume(self.tokens)
        candidate = (
            AppliedRateLimit(rate_limit, self.tokens)
            if self.expose_headers and rate_limit.reset_at is not None
            else None
        )

        if not rate_limit.is_accepted():
            # A refusing limit speaks for the response, even to say nothing.
            setattr(request.state, STATE_KEY, candidate)
            if container.has(EventDispatcherInterface):
                dispatcher = await container.get(EventDispatcherInterface)
                _ = await dispatcher.dispatch(
                    RateLimitExceededEvent(rate_limit, self.limiter, key),
                )
            raise TooManyRequestsError(rate_limit, self.limiter, key, Clock().now().timestamp())

        applied = applied_rate_limit(request)
        if candidate is not None and (
            applied is None or candidate.remaining_calls < applied.remaining_calls
        ):
            setattr(request.state, STATE_KEY, candidate)

    async def _key_of(self, request: Request) -> str:
        """Return what ``request`` is counted under.

        Raises:
            InvalidRateLimitError: When the key function returns anything
                but a string.
        """
        if self.key is None:
            client = request.client.host if request.client is not None else "unknown"
            # The route's template, not the path: /books/1 and /books/2 share one count, so
            # varying a path parameter never earns a fresh limit.
            route: object = request.scope.get("route")
            path = getattr(route, "path_format", None)
            return (
                f"{client}~{request.method}~{path if isinstance(path, str) else request.url.path}"
            )
        if isinstance(self.key, str):
            return self.key
        key: object = self.key(request)
        if inspect.isawaitable(key):
            key = await key
        if not isinstance(key, str):  # pyright: ignore[reportUnnecessaryIsInstance] -- the application's function; its annotation is not enforced
            raise InvalidRateLimitError(  # pyright: ignore[reportUnreachable] -- as above
                f'The key of the "{self.limiter}" rate limit must be a string, got {key!r}.',
            )
        return key


async def _configured(container: ContainerInterface | None) -> tuple[str, ...]:
    """Return the names the application configured limiters under; none without a kernel."""
    if container is None:
        return ()
    # The bundle's configuration names every limiter; only its bundle registers it.
    from xtr_rate_limiter.bundle import RateLimiterConfig  # noqa: PLC0415

    if not container.has(RateLimiterConfig):
        return ()
    config = await container.get(RateLimiterConfig)
    return tuple(sorted(config.limiters))
