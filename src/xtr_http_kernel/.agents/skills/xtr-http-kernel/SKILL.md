---
name: xtr-http-kernel
description: The HTTP entry point for a FastAPI application on xtr-dependency-injection — setup(app, kernel), routes bundles contribute and applications arrange, a request lifecycle of five events, container services injected into routes, the request and the response as HTTP messages, and rate limits on routes. Use when wiring a FastAPI app to a kernel, shipping a bundle's routes with @as_route_loader, moving, prefixing or leaving out a bundle's routes in config/routes with @as_routes, writing a route that needs a container service, injecting ServerRequestInterface or ResponseInterface, adding a request id or response header to every response, logging uncaught exceptions, turning an exception into a response, opening a per-request unit of work, contributing middleware from a bundle, listing routes with debug:router, rate limiting a route, or testing a served application. For plain FastAPI matters use the fastapi skill instead.
---

# xtr-http-kernel

FastAPI still routes, resolves arguments and serializes. This package adds the part around the
endpoint: one `setup(app, kernel)` call that gives every application life its own kernel, five
lifecycle events listeners can join, and container services injected straight into route
signatures. Everything the framework already does well is left alone.

## Quick reference

- One call: `setup(app, kernel)` from `xtr_http_kernel`, after the routes and before the first
  request. It compiles the kernel once and adds every route bundles contribute.
- Ship a bundle's routes with `@as_route_loader("resource")` on a class with `load_routes()`;
  arrange them in `<app>/config/routes/*.py` with `@as_routes` functions. See
  [Routes](#routes).
- Pull a container service into a route with `Injected[T]`, `Annotated[T, Target("name")]` or
  `Annotated[T, Autowire(param=...)]`. Keep `Depends` for everything that is the framework's.
- Take the request as a message with `Injected[ServerRequestInterface]`, the response with
  `Injected[Response]` — `xtr_http_kernel.bridge.Response` — and return it as it is, with the
  route annotated `-> Response`. A library takes `ResponseInterface` instead and is handed that
  same response.
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

`setup` compiles the kernel once — no service is built, no I/O — and adds its route table to the
application, so `app.routes` holds every route from then on. Configuration and the environment
are read at that moment. Then it wraps two seams:

- **The lifespan.** The first life boots the kernel `setup` compiled; later lives build it
  afresh. Each applies test overrides, boots, attaches the container so the route markers
  resolve, runs the app's own lifespan inside, then detaches and shuts down.
- **One middleware.** Fetches the kernel's `MiddlewareStack` once per life and runs every
  request through it, inside the request scope scoped services live in.

Serve it with any ASGI server: `uvicorn app.web:app`.

## Routes

A bundle ships a route loader; it is built with no arguments while the kernel compiles, so what it
contributes is fixed by its code:

```python
from xtr_http_kernel.routing import Route, RouteCollection
from xtr_http_kernel.routing.decorator import as_route_loader


async def list_books() -> list[str]:
    return ["Dune"]


@as_route_loader("books")
class BooksRouteLoader:
    def load_routes(self) -> RouteCollection:
        routes = RouteCollection()
        routes.add("books_list", Route("/books", list_books, methods=("GET",)))
        return routes
```

The application arranges contributed routes in `<app>/config/routes/` (a package — xtr-recipes
creates its `__init__.py` with the first routes file a recipe writes there):

```python
from xtr_http_kernel.routing.decorator import as_routes
from xtr_http_kernel.routing.loader.configurator import RoutingConfigurator


@as_routes
def shop(routes: RoutingConfigurator) -> None:
    routes.import_("books").prefix("/shop").name_prefix("shop_")
    routes.add("shop_books_list", "/shop/catalogue")  # move one route by its name
```

A resource no routes file imports or skips is served at its own paths. A mistake fails `setup`
with `InvalidArgumentError`; a contributed route sharing a name or a method and path with one the
application declared fails it with `RouteConflictError`. Every configurator call and rule:
[references/routing.md](references/routing.md).

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

## Take the request and the response as messages

```python
from xtr_dependency_injection import Injected
from xtr_http_message_contracts import ServerRequestInterface

from xtr_http_kernel.bridge import Response


@app.post("/tokens")
async def issue(
    request: Injected[ServerRequestInterface],
    response: Injected[Response],
) -> Response:
    _ = await response.get_body().write(await issuer.issue(request))
    return response.with_status(201).with_header("content-type", "application/json")
```

- Built only when asked, from the framework's own request: the body it read and the form it
  parsed, never a second reading of the wire. A route that does not ask pays nothing.
- Both are `lifetime="scoped"`: one request message and one response per request.
  `RequestInterface` and `MessageInterface` lead to the same request.
- `Response` and `ResponseInterface` lead to the same response: a route asks for the class at
  both ends, so parameter and return annotation agree with nothing to narrow, and a library
  that knows only the contract is handed that very object.
- The injected response *is* a FastAPI response, so return it as it is. Its status, headers and
  body are read when it is sent, so a body written with
  `await response.get_body().write(...)` after it was handed over is the body sent; the request
  id header and every `ResponseEvent` listener still apply. Read a body back through the message,
  with `await response.get_body().get_contents()`.
- **Every response in an application comes from one of two places**: the injected
  response, or the injected response factory. Every response that factory makes, and every
  response a `with_*` on either returns, is `xtr_http_kernel.bridge.Response`
  and is returned as it is — nothing to configure: no default response class, no encoder, no
  route class. A route making responses of its own asks for `ResponseFactory`, the class, and
  stays typed through every `with_*`; `ResponseFactoryInterface` is the same service, for a
  library that knows only the contract.
  **Never build an `xtr_http_message` response or `HttpFactory` in code that serves
  a request**: those classes know nothing of this framework, so one returned from a route is not
  something it can send. They are for code outside a served application — tests, workers,
  console commands. A message that arrived from there is sent with
  `await StarletteHttpFactoryInterface.create_response(message)`.
- `get_query_params()` and the parsed body of a submitted form are the framework's own
  `QueryParams` and `FormData`, so `getlist("a")` works and `items[]` is that name literally.
  Uploaded files wrap what the framework parsed where it lies; a field with no file reports
  `UploadError.NO_FILE`.
- The six message factories are registered too: `ResponseFactoryInterface` builds returnable
  responses, the other five come from `xtr_http_message`'s `HttpFactory`.
  `HttpMessageFactoryInterface` turns the framework's own into messages;
  `StarletteHttpFactoryInterface` turns a message into the framework's own, which is how a
  response built elsewhere is sent.
- Neither direction alters what it is handed. `create_response(response)` refuses a response
  that streams its body with `StreamedResponseBodyError` — reading it would consume it and
  leave the response unsendable, so build the message from the content being streamed instead —
  and one declaring a `Content-Range` with `RangedResponseBodyError`, since the message would
  carry the whole file under a header saying it carries one part of it.
  `create_request(message)` refuses a cookie a `Cookie` header cannot carry unchanged with
  `InvalidCookieError`, naming it: a value holding `;` would be read back as further cookies.
- Nothing about FastAPI's `Form`, `File`, `Body`, query and JSON parameters or its `422` bodies
  changes, with or without these on the route.

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
`HttpKernelBundle`. That is the steps below a recipe can do; the `setup(app, kernel)` step it
prints for you to make.

1. **Install** `uv add "xtr-http-kernel[logging,console]"`. The extras: `logging` adds the
   listeners that write to a log, `console` the router commands, `rate-limiter` the rate limits.
   None is needed to serve requests. The two message packages come with it, not behind an extra,
   and so does the parser a submitted form with files in it is read with: building the request as
   a message asks the framework for the form behind every multipart body.
2. **Activate** `HttpKernelBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`, imported
   from `xtr_http_kernel.bundle`, then call `setup(app, kernel)` where the application is built.
3. **Brings along** the event dispatcher bundle always; the logging, console and rate limiter
   bundles whenever those packages are installed. Installing the extra is what activates them,
   not listing.
4. **Configure** nothing by default: a fresh `uuid4` id under
   `X-Request-Id` per request (an inbound one is not trusted), no robots header, the `request`
   log channel.

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
| `InvalidCookieError` | a request message being turned into the framework's own carries a cookie a `Cookie` header cannot carry unchanged; also a `ValueError` |
| `InvalidMiddlewarePriorityError` | a `http_kernel.middleware` tag's `priority` is not an integer |
| `InvalidRateLimitError` | a `RateLimited` takes fewer than one token, limits a router that already has routes, or its key function returns no string; also a `ValueError` |
| `RangedResponseBodyError` | a response being turned into a message declares one range of the file it reads its body from |
| `ResponseAlreadyAMessageError` | a response being turned into a message is the bridge's own, which already is a message: there is nothing to convert |
| `StreamedResponseBodyError` | a response being turned into a message streams its body, which cannot be read without consuming it |
| `TooManyRequestsError` | a limiter refused the request; a 429 the framework answers, with `Retry-After` |
| `UnknownRateLimiterError` | a `RateLimited` names a limiter the application did not configure; also a `LookupError` |
| `UnsupportedConnectionError` | something asked for the request as a message while a WebSocket was being served |

A route marker resolving with no kernel attached, or outside a request scope, raises
`FastapiIntegrationError` from xtr-dependency-injection.

The route table's errors import from `xtr_http_kernel.routing`, under `RoutingError` (an
`HttpKernelError`): `InvalidArgumentError` (also the library's own, so a `ValueError`),
`RouteConflictError`, `RouteCircularReferenceError` — see
[references/routing.md](references/routing.md).

## Do not

- Do not `app.include_router(...)` a bundle's routes by hand: `setup` adds them, and including
  them again collides with them.
- Do not give a route loader constructor parameters: it is built with none, before any service
  exists.
- Do not use `Depends` to reach a container service. Use `Injected[T]` or `Target("name")`, so
  the service stays out of the OpenAPI schema.
- Do not call `attach`, `detach`, `request_scope`, `provider` or `current_connection` from
  `xtr_dependency_injection.integration.fastapi`. They are what `setup` is built on; an
  application calls `setup` and nothing lower. To reach the request being served, take the
  framework's own `request: Request` in a route, or `Injected[ServerRequestInterface]` in a
  route — a plain `ServerRequestInterface` parameter in a service — for the request as a
  message.
- Do not call `setup` after the application has started. The framework refuses new middleware
  then, and the lifecycle would be missing.
- Do not use `TestClient`, and do not drive the app without entering its lifespan: no kernel is
  attached, so every marker fails.
- Do not expect a body on `ResponseEvent`. Answer at `RequestEvent` or `ExceptionEvent` instead.
- Do not expect a service to be reset between requests. Concurrent requests share whatever is
  built for the application's life, so nothing is cleared per request; a service that must not
  outlive one request is registered `lifetime="scoped"`.
- Do not give a singleton a `ServerRequestInterface` or a `Response` parameter. Both belong to
  one request, so the container refuses it at build time; make the service `lifetime="scoped"`
  or transient.
- Do not annotate a route `-> ResponseInterface`, and do not write a bare
  `ServerRequestInterface` parameter: FastAPI fails the route at definition, since it can make
  no schema of either. Annotate `-> Response` and take `Injected[Response]`.
- Do not construct `xtr_http_message.Response(...)`, `xtr_http_message.factory.HttpFactory()`
  or any other concrete message class in a route, a listener or a per-request service. Take the
  registered factory interface instead; those classes belong to code that is not serving a
  request.
- Do not look for a controller, controller-arguments or view event. Routing, argument resolution
  and serialization are the framework's, deliberately.
