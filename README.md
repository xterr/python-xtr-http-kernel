<div align="center">

# xtr-http-kernel

**Requests turned into responses through events: a request lifecycle for FastAPI applications on the xtr kernel.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

A web framework routes a request to the function that answers it, and that is the part worth
writing by hand. Everything an application wants *around* that function — a request id on every
response, an uncaught exception written to the log with the request that caused it, a header
keeping a page out of a search index — is not the endpoint's business, and repeating it in each
endpoint is how it comes to be missing from one.

This library puts those between the framework and the endpoint as **events**: a request
announces itself, the response it produced announces itself, and whoever listens contributes.
Listeners are services, so they come from the container with everything else they need.

- 🔁 **The framework stays the framework.** Routes, `Depends`, request bodies, serialization and
  the generated schema are FastAPI's, untouched.
- 🧩 **Listeners are services.** Registered by a bundle, injected like any other collaborator.
- 🪝 **A lifecycle you can join.** Contribute at the request, at the response, at an uncaught
  exception, and once everything has been sent.
- 🪪 **A request id for free.** Every response carries one; every log record made while handling
  carries the same.

## Install

```sh
uv add xtr-http-kernel                      # the lifecycle, its bundle and setup
uv add "xtr-http-kernel[logging]"           # + the listeners that log
uv add "xtr-http-kernel[console]"           # + the commands that report on the router
uv add "xtr-http-kernel[rate-limiter]"      # + rate limits on routes, routers and the app
```

Requires Python 3.11+. The web framework and the container layer come with the package
itself — this *is* the integration — so neither is an extra.

## Quick start

Write the application the way FastAPI documents it, list the bundle, and hand the app to
`setup` beside the kernel. The kernel scans the module, so the listener below is registered
without another line:

```python
# app.py
from __future__ import annotations

from fastapi import FastAPI
from xtr_dependency_injection import Kernel
from xtr_event_dispatcher import as_event_listener
from xtr_http_kernel import ResponseEvent, setup
from xtr_http_kernel.bundle import HttpKernelBundle


# A service the container registers, keyed by the event it is annotated with.
@as_event_listener()
def name_the_server(event: ResponseEvent) -> None:
    event.headers["server"] = "bookshop"


app = FastAPI()


@app.get("/books/{isbn}")
async def read_book(isbn: str) -> dict[str, str]:
    return {"isbn": isbn}


kernel = Kernel("app", bundles={HttpKernelBundle: {"all": True}})
setup(app, kernel)
```

Serve it with any ASGI server:

```sh
uv run --with uvicorn uvicorn --app-dir . app:app
```

```console
$ curl -i localhost:8000/books/0262510871
HTTP/1.1 200 OK
server: bookshop
x-request-id: 5f4e8c1a3b2d4e6f9a0b1c2d3e4f5a6b
content-type: application/json

{"isbn":"0262510871"}
```

The `x-request-id` and the `server` header are the two listeners at work: one shipped with the
bundle, one written above.

## What `setup` does

`setup(app, kernel)` is the one call an application makes. It changes nothing about how routes
are declared; it wraps two seams around them:

- **The lifespan.** Every start of the application's lifespan builds the kernel afresh, boots
  it — a built container boots once, and a test starts the application many times — and attaches
  the container so the injection markers resolve in routes. The application's own lifespan runs
  inside, its state passing through untouched; on the way out the container is detached and shut
  down.
- **One middleware.** Added when `setup` is called, so **call it before the first request** —
  after the routes and the application's own middleware is fine. Each life fetches the
  [middleware stack](#middleware-from-a-bundle) the kernel's bundles contributed and runs every
  request through it, inside the request scope the scoped services live in.

An application that has already started refuses new middleware; the framework's own error
surfaces then, rather than a request running without its lifecycle.

## The lifecycle

Every request goes through the same events, and a listener joins wherever it has something to
contribute. Each is dispatched at most once, however the request went:

| Event | `KernelEvents` | When | What a listener may do |
|---|---|---|---|
| `RequestEvent` | `REQUEST` | it arrived, nothing has looked at it | read it, or `set_response(...)` to answer instead of the application |
| `ResponseEvent` | `RESPONSE` | a response is about to start | assign `status_code`, change `headers` in place |
| `ExceptionEvent` | `EXCEPTION` | handling raised, nothing was sent | read `exception`, or `set_response(...)` to answer with it |
| `FinishRequestEvent` | `FINISH_REQUEST` | handling finished — **on every path** | put away what the request set up |
| `TerminateEvent` | `TERMINATE` | everything was sent | work worth doing once the caller has their answer |

`RequestEvent.set_response` and `ExceptionEvent.set_response` stop the event: the listeners
after them do not run, because the request has been dealt with. A response is streamed, so
`ResponseEvent` carries no body — only the head, which has not left yet, so a listener owns
exactly `status_code` and `headers`. A listener wanting to answer with a body of its own does
so at the request or the exception, where nothing has been sent.

`ExceptionEvent` fires only while nothing has been sent. Once the response has started, a
failure part-way through the body cannot be turned into a response, so the exception goes back
out as it arrived — turning it into a response is the application's job, not the lifecycle's.
`FinishRequestEvent` runs on every path, which is what makes it the place to close what a
request opened; `TerminateEvent` carries the status that actually left, `500` when an
unanswered exception left before the response started.

Events are keyed by the qualified name of their class, so a listener declared on a typed
parameter and one registered under the matching `KernelEvents` constant are the same
registration. The constants exist for the places a class cannot be written — a listener whose
event is chosen at runtime, a subscriber mapping names to methods:

```python
from xtr_event_dispatcher import as_event_listener

from xtr_http_kernel import KernelEvents, ResponseEvent


# Declared for a container to register, keyed by the annotated event…
@as_event_listener(priority=100)
def keep_it_out_of_the_index(event: ResponseEvent) -> None:
    event.headers["x-robots-tag"] = "noindex"


# …or registered by hand, under the same name.
dispatcher.add_listener(KernelEvents.RESPONSE, keep_it_out_of_the_index, priority=100)
```

## What FastAPI already does

The lifecycle deliberately stops at the endpoint's door. FastAPI **routes** the request,
**resolves the endpoint's arguments** — path and query parameters, request bodies, `Depends`
and container markers alike — and **serializes** the return value, and it does all of that
better than a re-implementation would. So there is no controller event, no
controller-arguments event and no view event: the moments those would name are the framework's,
and the generated OpenAPI schema stays the framework's too.

What is left for the lifecycle is everything *around* the endpoint — the id, the log line, the
header, the unit of work — and that is all it does.

## Scoped services

A service registered `lifetime="scoped"` is built once per request and **released after the
response has been sent** — FastAPI's own timing for a dependency's cleanup. A service that
opens a unit of work per request therefore commits or rolls back once the caller has their
answer, and a generator factory's cleanup runs then. Put cleanup that must survive an error in
a `finally`: the engine throws a scope's error into the generator, so a commit that fails
raises there, and — with the logging listeners active — that failure is written to the log
against the request that caused it, like any other uncaught exception.

## Listeners shipped

The bundle registers these; which ones depend on what is installed and active:

| Listener | Events | Active when | Does |
|---|---|---|---|
| `RequestIdListener` | `RequestEvent`, `ResponseEvent` | always | keeps a trusted incoming id or mints a `uuid4().hex`, puts it on `request.state.request_id`, binds it to the log context when logging is around, and echoes it on the response |
| `DisallowRobotsIndexingListener` | `ResponseEvent` | always | stamps `X-Robots-Tag: noindex` on every response, when the config turns it on |
| `LogUnitListener` | `RequestEvent`, `TerminateEvent` | logging bundle active | opens a [logging unit of work](../xtr-logging#units-of-work) per request and closes it once all was sent |
| `ErrorLoggingListener` | `ExceptionEvent` | logging bundle active | writes every uncaught exception to the request channel — `error` below a 500 status, `critical` otherwise — leaving the response to whoever answers it |
| `RateLimitHeadersListener` | `ResponseEvent` | rate limiter bundle active | writes the `X-RateLimit-*` headers of the [rate limit](#rate-limits) that speaks for the response, and makes it private |

The two logging listeners join only when the logging bundle is active, and open and close the
unit of work outside everything else so every record made while handling carries the request's
id. The request id settles right after the unit opens, for the same reason.

## Rate limits

With the `rate-limiter` extra, a route, a router or the whole application can be held to a
limiter configured in [xtr-rate-limiter](../xtr-rate-limiter)'s bundle. `RateLimited` is one
declaration, written as a decorator or wherever the framework takes a dependency:

```python
from fastapi import APIRouter, FastAPI, Request

from xtr_http_kernel.rate_limiter import RateLimited

app = FastAPI(dependencies=[RateLimited("global")])  # every route


@app.get("/books")
@RateLimited("api", expose_headers=True)  # below the route decorator
async def list_books() -> list[Book]: ...


def by_username(request: Request) -> str:
    return request.headers.get("x-username", "anonymous")


@app.post("/login", dependencies=[RateLimited("login", key=by_username, methods="post")])
async def login() -> None: ...


reports = RateLimited("reports")(APIRouter(prefix="/reports"))  # before its routes
app.include_router(admin, dependencies=[RateLimited("admin")])  # or when included
```

- **Where it runs.** After routing and before the endpoint: routing is the framework's, so the
  limit is a dependency rather than a lifecycle listener, and runs in the framework's order —
  the application's, the routers', then the route's. As a decorator it must sit **below** the
  route decorator, which reads the endpoint when the route is declared; a router must be
  limited **before** routes are added, since each route copies its router's dependencies.
- **What a request is counted under.** `key` is a string, or a function of the request —
  awaited when it returns an awaitable. By default: the client's address, the method and the
  route's path template — `/books/{isbn}`, so asking for another book never earns a fresh
  limit. Behind a proxy the address is the proxy's unless the server trusts its forwarded
  headers (uvicorn's `--forwarded-allow-ips`).
- **`tokens`** a request consumes, and **`methods`** limited — every one when empty; `GET` also
  limits `HEAD`.
- **A refusal** is answered `429 Too Many Requests` with `Retry-After`, raised as
  `TooManyRequestsError` — the framework's own HTTP exception, so an exception handler
  registered for it reshapes the body. A `RateLimitExceededEvent` naming the limiter and the key
  is dispatched first. Limits consulted before a refusal keep their spend.
- **Headers.** With `expose_headers=True` the response carries `X-RateLimit-Limit`,
  `X-RateLimit-Remaining` and `X-RateLimit-Reset`, in calls rather than tokens, for the limit
  closest to refusing among those exposing theirs; a refusing limit always speaks, and one that
  keeps its state to itself leaves the response without them. The response is made private, so
  a shared cache never serves one caller's count to another.
- **The published schema** is untouched: the limit never appears as a parameter.

A limiter the application did not configure fails the request with `UnknownRateLimiterError`,
naming the ones it did. To limit by hand — throttling logins only on failure, say — inject the
limiter by name like any service:

```python
from typing import Annotated

from xtr_dependency_injection import Target
from xtr_rate_limiter import RateLimiterFactoryInterface


@app.post("/login")
async def login(
    limiter: Annotated[RateLimiterFactoryInterface, Target("login")],
) -> None:
    limit = limiter.create(username)
    if not (await limit.consume(0)).is_accepted():
        raise TooManyAttempts
    ...
```

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what
removing it undoes.

- **Install** — `uv add "xtr-http-kernel[logging,console]"`; `logging` brings the listeners
  that write to a log, `console` the commands that report on the router, `rate-limiter` the
  [rate limits](#rate-limits). None is needed to serve requests.
- **Activate** — `HttpKernelBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`, imported
  from `xtr_http_kernel.bundle`. Then call `setup(app, kernel)` where the application is built.
- **Brings along** — the [event dispatcher](../xtr-event-dispatcher) bundle always, because the
  lifecycle dispatches through it; the [logging](../xtr-logging), [console](../xtr-console) and
  [rate limiter](../xtr-rate-limiter) bundles whenever those packages are *installed* — they are required peers, pulled in and made
  active without being listed, and left out silently when the package is not installed. Listing
  is not what activates them; installing the extra is.
- **Configure** — nothing is required: the zero-config path gives a `uuid4` request id under
  `X-Request-Id`, no robots header, and the `request` log channel. A
  `<app>/config/http_kernel.py` `@configure` function returning an `HttpKernelConfig` changes
  that — see [Configure](#configure) and [Kernel / bundle](#kernel--bundle).
- **Environment** — nothing.
- **Ignore** — nothing.
- **Remove** — drop the `setup(app, kernel)` call, drop the `BUNDLES` entry, delete
  `<app>/config/http_kernel.py` if you wrote one, then `uv remove xtr-http-kernel`.
- **Check** — `debug:bundles` shows `http_kernel` as `listed` and `active`, `event_dispatcher`
  as `required`, and (with the extras) `logging` and `console` as `required`; `debug:router`
  lists the application's routes.

## Configure

`HttpKernelConfig` is a frozen dataclass buildable with no arguments; every field has a
default:

| Field | Default | What it sets |
|---|---|---|
| `request_id_header` | `"X-Request-Id"` | the header the id is read from and echoed on; must be a non-empty HTTP token |
| `trust_request_id` | `True` | keep a well-formed incoming id; `False` mints a fresh one every request |
| `disallow_search_indexing` | `False` | mark every response `X-Robots-Tag: noindex` |
| `log_channel` | `"request"` | the channel the error listener writes to |
| `middleware_priority` | `0` | where the lifecycle middleware sits among the contributed factories — highest outermost |
| `app` | `None` | the `"package.module:app"` string the router commands load the application from |

The constructor refuses values the lifecycle would silently misread: a `request_id_header` that
is not an HTTP token, an empty `log_channel`, or an `app` that is not exactly one module and one
attribute around a single `:`, each raise `ValueError`.

The bundle declares the default `log_channel` on the logging config for you. An application
renaming it must declare the new channel in its own logging configuration — this bundle's
config resolves after logging's, so it cannot declare a name it does not yet know.

## Kernel / bundle

An application using [xtr-dependency-injection](../xtr-dependency-injection) lists
`HttpKernelBundle` in its `app/bundles.py`:

```python
# app/bundles.py
from xtr_http_kernel.bundle import HttpKernelBundle

BUNDLES = {HttpKernelBundle: {"all": True}}
```

```python
# app/config/http_kernel.py
from xtr_dependency_injection import configure

from xtr_http_kernel.bundle import HttpKernelConfig


@configure
def http_kernel() -> HttpKernelConfig:
    return HttpKernelConfig(disallow_search_indexing=True, app="app.web:app")
```

The bundle registers the lifecycle middleware factory, the listeners, and — when a console
bundle is active — the router commands. It requires the event dispatcher bundle outright, and
the logging and console bundles when installed. Its zero-config path builds and boots with no
application configuration and touches no I/O until a request arrives.

## Middleware from a bundle

The lifecycle middleware is one entry in an ordered chain that any bundle can add to. A bundle
tags a service that builds a middleware — a callable taking the downstream ASGI app and
returning it wrapped — with `MIDDLEWARE_TAG` (`"http_kernel.middleware"`) and an integer
`priority`:

```python
from xtr_http_kernel import MIDDLEWARE_TAG

services.set(compression_middleware).add_tag(MIDDLEWARE_TAG, priority=10)
```

When the kernel is built, the http_kernel bundle orders every tagged factory into a
`MiddlewareStack` — highest `priority` outermost, so it sees the request first; a missing
`priority` counts as `0`, and ties keep registration order. `setup` fetches the stack once per
application life and composes it over the application, inside the request scope. A `priority`
that is not an integer fails the build with `InvalidMiddlewarePriorityError`, naming the
offending definition.

## Router commands

With a console bundle active, two commands read the application without serving it:

- **`debug:router`** lists every route in the order routing tries them, prefixes and mounts
  applied.
- **`router:match PATH [--method GET]`** names the route a path reaches, reports a route that
  matches the path but refuses the method as the near miss it is, and fails on a path no route
  answers.

Both take the application from `--app "package.module:app"`, or from `HttpKernelConfig.app`
when the option is left out, and read it either side of FastAPI's move to lazily included
routers.

## Testing

FastAPI's `TestClient` is unusable here: it leans on a deprecated framework path, and this
package's test suite turns warnings into errors. Drive the application through an ASGI transport
instead, inside its own lifespan so `setup`'s wrapper builds and boots the kernel:

```python
import httpx
import pytest

from app import app


@pytest.mark.anyio
async def test_a_book_carries_a_request_id() -> None:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/books/0262510871")

    assert response.status_code == 200
    assert response.headers["x-request-id"]
```

To swap a service for the span of a test, park the replacements on the application with
`override_services` **before** entering the lifespan, so every kernel built while the block is
open — every boot hook, every route — sees them:

```python
from xtr_http_kernel.testing import override_services


@pytest.mark.anyio
async def test_it_uses_the_fake_catalogue() -> None:
    with override_services(app, {Catalogue: FakeCatalogue()}):
        async with app.router.lifespan_context(app):
            ...  # requests here resolve the fake
```

A key is a type, or a `(type, qualifier)` pair for a qualified service.

## Errors

Everything this library raises derives from `HttpKernelError`, and carries what went wrong as
typed attributes rather than only a message.

| Error | Raised when |
|---|---|
| `InvalidMiddlewarePriorityError` | a `http_kernel.middleware` tag's `priority` is not an integer |

## Layout

| `InvalidRateLimitError` | a `RateLimited` takes fewer than one token, limits a router that already has routes, or its key function returns no string; also a `ValueError` |
| `TooManyRequestsError` | a limiter refused the request — a 429 the framework answers, with `Retry-After` |
| `UnknownRateLimiterError` | a `RateLimited` names a limiter the application did not configure; also a `LookupError` |
```
xtr_http_kernel/
├── setup.py                        setup(app, kernel), the one call an application makes
├── testing.py                      override_services, for a served application under test
├── event/                          the five lifecycle events, one class per file
├── kernel_events.py                KernelEvents, the name each of them is dispatched under
├── event_listener/                 the listeners the bundle registers
├── request_lifecycle_middleware.py the middleware that dispatches the events
├── middleware_stack.py             the ordered chain a bundle contributes to
├── middleware_tag.py               MIDDLEWARE_TAG, the tag bundles agree on
├── command/                        debug:router and router:match
├── exception/                      HttpKernelError, the root of everything this library raises
└── bundle/                         HttpKernelBundle and HttpKernelConfig
├── rate_limiter/                   RateLimited, with the rate-limiter extra
```

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-http-kernel`; run the commands below from there. The `python-xtr-http-kernel`
repository is a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync --all-extras
uv run ruff check
uv run ruff format --check
uv run basedpyright
uv run ty check
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
</content>
</invoke>
