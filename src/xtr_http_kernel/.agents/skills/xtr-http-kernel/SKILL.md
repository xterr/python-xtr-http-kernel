---
name: xtr-http-kernel
description: The HTTP entry point for a FastAPI application built on xtr-dependency-injection — setup(app, kernel), a request lifecycle of five events, container services injected into routes, and rate limits on routes. Use when wiring a FastAPI app to a kernel, writing a route that needs a container service, adding a request id or a response header for every request, logging uncaught exceptions with the request that caused it, short-circuiting a request before routing, turning an exception into a response, opening a per-request unit of work, contributing middleware from a bundle, listing routes with debug:router, rate limiting a route or router, or testing a served application with an httpx ASGI client. For plain FastAPI matters (routing, Depends, request bodies, response models, OpenAPI) use the fastapi skill instead.
---

# xtr-http-kernel

FastAPI still routes, resolves arguments and serializes. This package adds the part around the
endpoint: one `setup(app, kernel)` call that gives every application life its own kernel, five
lifecycle events listeners can join, and container services injected straight into route
signatures. Everything the framework already does well is left alone.

## Quick reference

- One call: `setup(app, kernel)` from `xtr_http_kernel`, after the routes and before the first
  request.
- Pull a container service into a route with `Injected[T]`, `Annotated[T, Target("name")]` or
  `Annotated[T, Autowire(param=...)]`. Keep `Depends` for everything that is the framework's.
- Join the lifecycle with `@as_event_listener()` from `xtr_event_dispatcher` on a function
  taking one of `RequestEvent`, `ResponseEvent`, `ExceptionEvent`, `FinishRequestEvent`,
  `TerminateEvent`.
- Every response carries a freshly minted `X-Request-Id`; `request.state.request_id` holds the
  same value. An inbound id is ignored unless `trust_request_id=True`.
- Test with `httpx.ASGITransport` inside `app.router.lifespan_context(app)`, never
  `TestClient`. Swap services with `override_services` from `xtr_http_kernel.testing`.
- Activate `HttpKernelBundle` from `xtr_http_kernel.bundle`; configure with `HttpKernelConfig`.

## Set up the application

```python
# app/web.py
from __future__ import annotations

from fastapi import FastAPI
from xtr_dependency_injection import Kernel
from xtr_http_kernel import setup
from xtr_http_kernel.bundle import HttpKernelBundle

app = FastAPI()
# ... routes and the application's own middleware here ...

kernel = Kernel("app", bundles={HttpKernelBundle: {"all": True}})
setup(app, kernel)
```

`setup` builds nothing. It wraps two seams:

- **The lifespan.** Every application life builds the kernel afresh, applies test overrides,
  boots it, attaches the container so the route markers resolve, runs the app's own lifespan
  inside, then detaches and shuts down.
- **One middleware.** Fetches the kernel's `MiddlewareStack` once per life and runs every
  request through it, inside the request scope scoped services live in.

Serve it with any ASGI server: `uvicorn app.web:app`.

## Inject services into a route

```python
from typing import Annotated

from xtr_dependency_injection import Autowire, Injected, Target


@app.get("/books/{isbn}")
async def read_book(
    isbn: str,  # a path parameter, the framework's
    catalogue: Injected[Catalogue],  # from the container
    mailer: Annotated[Mailer, Target("smtp")],  # a qualified service
    env: Annotated[str, Autowire(param="kernel.environment")],  # a kernel parameter
) -> Book:
    return await catalogue.get(isbn)
```

The markers never reach the OpenAPI schema, so the documented parameters stay the HTTP ones. A
`lifetime="scoped"` service is built once per request and released after the response has been
sent, which is when a per-request unit of work commits or rolls back; put cleanup that must
survive an error in a `finally`.

## Join the lifecycle

```python
from fastapi import Response
from xtr_event_dispatcher import as_event_listener

from xtr_http_kernel import ExceptionEvent, RequestEvent, ResponseEvent, TerminateEvent


@as_event_listener(priority=100)
def keep_it_out_of_the_index(event: ResponseEvent) -> None:
    event.headers["x-robots-tag"] = "noindex"  # headers are the outgoing ones, mutated in place


@as_event_listener()
def serve_the_maintenance_page(event: RequestEvent) -> None:
    if under_maintenance():
        event.set_response(Response("back soon", status_code=503))  # the app never runs


@as_event_listener()
def answer_the_failure(event: ExceptionEvent) -> None:
    if isinstance(event.exception, OutOfStock):
        event.set_response(Response("sorry", status_code=409))


@as_event_listener()
def count_the_status(event: TerminateEvent) -> None:
    metrics.increment(event.status_code)  # the caller already has their answer
```

Every event carries `request`. The kernel scans the application package, so a listener in a
scanned module needs no further registration.

| Event | When | A listener may |
| --- | --- | --- |
| `RequestEvent` | it arrived, nothing has looked at it | read `request`, or `set_response(...)` to answer instead of the application |
| `ResponseEvent` | a response is about to start | assign `status_code`, mutate `headers`; there is no body here |
| `ExceptionEvent` | handling raised, nothing was sent | read `exception` (a `BaseException`), or `set_response(...)` to answer with it |
| `FinishRequestEvent` | handling finished, on every path | put away what the request set up |
| `TerminateEvent` | everything was sent | read `status_code`, which is `500` when nothing left |

- `set_response` stops the event: the listeners after it do not run.
- `ExceptionEvent` only fires while nothing has been sent, and only an `Exception` is turned
  into a response; a cancellation or an interrupt is announced and then carries on out.
- `ResponseEvent` owns exactly the head, because the body is streamed. A listener wanting a
  body of its own answers at the request or the exception.
- `KernelEvents.REQUEST`, `.RESPONSE`, `.EXCEPTION`, `.FINISH_REQUEST` and `.TERMINATE` name the
  same events, for a listener registered by hand:
  `dispatcher.add_listener(KernelEvents.RESPONSE, stamp, priority=100)`.

## What ships already

The bundle registers `RequestIdListener` and `DisallowRobotsIndexingListener` always,
`LogUnitListener` and `ErrorLoggingListener` when the logging bundle is active, and
`RateLimitHeadersListener` when the rate limiter bundle is. So a request id, a per-request
logging unit, an uncaught exception written to the log, a noindex header and the
`X-RateLimit-*` headers are all already done: configure them rather than writing your own. See
[references/listeners.md](references/listeners.md) for what each one does.

An uncaught exception is logged at `critical`, at `error` when it carries a `status_code` below
500, and at `info` when it is a cancellation, an interrupt or an exit — those say a timeout, a
gone caller or a shutdown reached the lifecycle, not that anything is broken.

## Rate limits

With the `rate-limiter` extra, `RateLimited` holds a route, a router or the whole application to
a limiter configured in xtr-rate-limiter's bundle:

```python
from xtr_http_kernel.rate_limiter import RateLimited

app = FastAPI(dependencies=[RateLimited("global")])  # every route


@app.get("/books")
@RateLimited("api", expose_headers=True)  # below the route decorator
async def list_books() -> list[Book]: ...
```

A refusal is `429 Too Many Requests` with `Retry-After`, raised as `TooManyRequestsError`.
See [references/rate-limits.md](references/rate-limits.md) for keys, tokens, methods, headers,
routers and limiting by hand.

## Contribute middleware from a bundle

A bundle tags a service that builds a middleware (a callable taking the downstream ASGI app and
returning it wrapped) with `MIDDLEWARE_TAG` from `xtr_http_kernel` and an integer `priority`:
`services.set(compression_middleware).add_tag(MIDDLEWARE_TAG, priority=10)`. Highest sits
outermost, a missing one counts as `0`, ties keep registration order, and a non-integer fails
the build with `InvalidMiddlewarePriorityError`.

## Testing

`TestClient` is unusable here: it leans on a deprecated framework path. Drive the application
through an ASGI transport, inside its own lifespan so the kernel builds and boots:

```python
import httpx
import pytest

from app.web import app


@pytest.mark.anyio
async def test_a_book_carries_a_request_id() -> None:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/books/0262510871")

    assert response.status_code == 200
    assert response.headers["x-request-id"]
```

Swap a service by parking it on the application **before** entering the lifespan:

```python
from xtr_http_kernel.testing import override_services


@pytest.mark.anyio
async def test_it_uses_the_fake_catalogue() -> None:
    with override_services(app, {Catalogue: FakeCatalogue()}):
        async with app.router.lifespan_context(app):
            ...  # every kernel built here resolves the fake
```

A key is a type, or a `(type, qualifier)` pair. The overrides live on the application, so two
tests serving one application must not run at the same time.

## Use in an application

`uv run xtr-recipes recipes:sync` applies the recipe shipped with this package: it lists
`HttpKernelBundle`. That is the steps below a recipe can do; the `setup(app, kernel)` step it prints
for you to make.

1. **Install** `uv add "xtr-http-kernel[logging,console]"`. The extras: `logging` adds the
   listeners that write to a log, `console` the router commands, `rate-limiter` the rate limits.
   None is needed to serve requests.
2. **Activate** `HttpKernelBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`, imported
   from `xtr_http_kernel.bundle`, then call `setup(app, kernel)` where the application is built.
3. **Brings along** the event dispatcher bundle always; the logging, console and rate limiter
   bundles whenever those packages are installed. Installing the extra is what activates them,
   not listing.
4. **Configure** nothing by default: a fresh `uuid4` id under `X-Request-Id` per request (an
   inbound one is not trusted), no robots header, the `request` log channel.

   ```python
   # <app>/config/http_kernel.py
   from xtr_dependency_injection import configure

   from xtr_http_kernel.bundle import HttpKernelConfig


   @configure
   def http_kernel() -> HttpKernelConfig:
       return HttpKernelConfig(disallow_search_indexing=True, app="app.web:app")
   ```

   Six fields, all optional: `request_id_header`, `trust_request_id`,
   `disallow_search_indexing`, `log_channel`, `middleware_priority`, `app`. See
   [references/configure.md](references/configure.md) for each one's default and meaning.
5. **Environment** nothing.
6. **Run** any ASGI server against the module `setup` was called in: `uvicorn app.web:app`.
7. **Check** `debug:bundles` shows `http_kernel` as `listed` and `active`, `event_dispatcher` as
   `required`. With a console bundle, `debug:router` lists the routes in the order routing tries
   them, and `router:match PATH [--method GET]` names the route a path reaches.
8. **Remove** drop the `setup(app, kernel)` call, drop the `BUNDLES` entry, delete
   `<app>/config/http_kernel.py`, then `uv remove xtr-http-kernel`.

## Errors

All derive from `HttpKernelError`, and import from `xtr_http_kernel` or
`xtr_http_kernel.exception`:

| Error | Raised when |
| --- | --- |
| `InvalidArgumentError` | an `HttpKernelConfig` field holds a value the lifecycle would misread; also a `ValueError` |
| `InvalidMiddlewarePriorityError` | a `http_kernel.middleware` tag's `priority` is not an integer |
| `InvalidRateLimitError` | a `RateLimited` takes fewer than one token, limits a router that already has routes, or its key function returns no string; also a `ValueError` |
| `TooManyRequestsError` | a limiter refused the request; a 429 the framework answers, with `Retry-After` |
| `UnknownRateLimiterError` | a `RateLimited` names a limiter the application did not configure; also a `LookupError` |

A route marker resolving with no kernel attached, or outside a request scope, raises
`FastapiIntegrationError` from xtr-dependency-injection.

## Do not

- Do not use `Depends` to reach a container service. Use `Injected[T]` or `Target("name")`, so
  the service stays out of the OpenAPI schema.
- Do not call `attach`, `detach`, `request_scope` or `provider` from
  `xtr_dependency_injection.integration.fastapi`. They are what `setup` is built on; an
  application calls `setup` and nothing lower.
- Do not call `setup` after the application has started. The framework refuses new middleware
  then, and the lifecycle would be missing.
- Do not use `TestClient`, and do not drive the app without entering its lifespan: no kernel is
  attached, so every marker fails.
- Do not expect a body on `ResponseEvent`. Answer at `RequestEvent` or `ExceptionEvent` instead.
- Do not expect a service to be reset between requests. Concurrent requests share whatever is
  built for the application's life, so nothing is cleared per request; a service that must not
  outlive one request is registered `lifetime="scoped"`.
- Do not look for a controller, controller-arguments or view event. Routing, argument resolution
  and serialization are the framework's, deliberately.
