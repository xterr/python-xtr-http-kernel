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
- ✉️ **The request and the response as messages.** Ask for them by the
  [HTTP message contract](../xtr-http-message-contracts) and a library that never heard of this
  web framework can read the one and fill in the other.

## Install

```sh
uv add xtr-http-kernel     # the lifecycle, its bundle and setup
uv add xtr-logging         # beside it: the listeners that log
uv add xtr-console         # beside it: the commands that report on the router
uv add xtr-rate-limiter    # beside it: rate limits on routes, routers and the app
```

Requires Python 3.11+. The web framework and the container layer come with the package
itself — this *is* the integration — and so do the
[HTTP message contract](../xtr-http-message-contracts) and
[its implementation](../xtr-http-message): the bridge below is made of them. The three
packages beside it are optional: each is used when it is installed and left alone when not.

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

`setup(app, kernel)` is the one call an application makes. It changes nothing about how the
application's own routes are declared; it adds the routes bundles contribute and wraps two seams
around them:

- **The routes.** `setup` compiles the kernel once — nothing is booted and no service is built
  — and adds its [route table](#routes) to the application with the framework's own
  `include_router`. From then on the application holds every route it serves, so whatever
  reads its routes — the [router commands](#router-commands), the API description,
  `url_path_for` — sees them all without starting it. Configuration and the environment are
  therefore read when `setup` runs, and a contributed route colliding with one the application
  declared itself fails right there.
- **The lifespan.** The first start of the application's lifespan boots the kernel `setup`
  compiled; every later start builds it afresh — a built container boots once, and a test starts
  the application many times. Each attaches the container so the injection markers resolve in
  routes. The application's own lifespan runs inside, its state passing through untouched; on
  the way out the container is detached and shut down.
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
| `ExceptionEvent` | `EXCEPTION` | handling raised, nothing was sent | read `exception`, or `set_response(...)` to answer with it — an `Exception` only: a cancellation, interrupt or exit is announced and goes on |
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

## The request and the response as messages

A library that reads a request and fills in a response should not have to know which web
framework the application runs on. It takes the
[HTTP message contract](../xtr-http-message-contracts) — `ServerRequestInterface`,
`ResponseInterface` — and this package hands it the request being served and a response to
answer with. An endpoint asks for the same two, naming the bridge's own `Response` where the
contract would do, so that what it returns is the type it declares:

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

- **Built only when asked.** The request is built the first time something asks for it, from
  FastAPI's own request object — the body it already read, the form it already parsed. A route
  that does not ask pays nothing, and nothing is buffered anywhere.
- **Once per request.** Both are `lifetime="scoped"`, so every endpoint, dependency and service
  of one request sees the same request message and the same response. `RequestInterface` and
  `MessageInterface` lead to the same build, so a parameter typed by any of the three gets it.
- **One response, two names.** `xtr_http_kernel.bridge.Response` and `ResponseInterface` lead to
  that same build: an endpoint asks for the class and declares it returns it — parameter and
  return annotation the same type, nothing to narrow and nothing to configure — while a library
  that knows only the contract asks for `ResponseInterface` and is handed that very response.
- **Returned as it is.** The injected response is `xtr_http_kernel.bridge.Response`: an
  HTTP message *and* a FastAPI response. Return it and it goes out — status, headers and
  body read at the moment of sending, so a body written through
  `await response.get_body().write(...)` after the response was handed over is the body on the
  wire. Assigning `response.body = ...` sets the body too; the body is read back through the
  message, with `await response.get_body().get_contents()`. The request id header and every
  `ResponseEvent` listener still apply to it, like any other response.
- **Every response in an application comes from one of those two.** Either it is the injected
  response, or the injected response factory made it — and every response that factory makes,
  and every response a `with_*` on either of them returns, is that same class. So there is
  nothing to configure: no default response class, no encoder registration, no route class of
  its own. Returning one is the whole of it. A route that makes responses of its own asks for
  `ResponseFactory`, the class, and stays typed through every `with_*`;
  `ResponseFactoryInterface` is the same service, for a library that knows only the contract.
  **Never build an `xtr_http_message` response or an `xtr_http_message.factory.HttpFactory` in
  code that serves a request:** those concrete classes know nothing of this web framework, so
  one of them returned from a route is not a response the framework can send. They are for code
  *outside* a served application — a test, a worker, a console command — and a message that
  arrived from there is sent by [converting it](#building-and-converting-messages).
- **Annotate the return `-> Response`.** FastAPI reads the return annotation to build the
  schema, and the class above is a response of its own, so the framework sends it rather than
  making a schema of it. A bare `ResponseInterface` annotation fails the route at definition,
  which is the framework telling you it cannot make a schema of a contract — so a route
  annotates the class at both ends and a strict type checker is satisfied with no narrowing.
- **Values are the framework's own.** `get_query_params()` and the parsed body of a submitted
  form are FastAPI's own `QueryParams` and `FormData`, handed over rather than copied: `["a"]`
  is the last value and `getlist("a")` is every value, and a bracketed name such as `items[]`
  is that name, literally. Uploaded files wrap what the framework parsed where it lies, so
  nothing is copied; a field submitted with no file reports `UploadError.NO_FILE`.
- **Per-request services only.** A service that takes a `ServerRequestInterface`, a `Response`
  or a `ResponseInterface` must be `lifetime="scoped"` or transient. A singleton would hold the
  request or the response of whichever request happened to build it, so the container refuses
  one at build time, naming the parameter.
- **A socket has no request message.** On a WebSocket route, asking for one raises
  `UnsupportedConnectionError`: take the framework's own `websocket: WebSocket` instead.

Nothing about FastAPI's own `Form`, `File`, `Body`, query and JSON parameters changes, with or
without these on the route — including its `422` bodies.

### Building and converting messages

The bundle also registers the six factories of the message contract, so a library can build a
message of its own: `RequestFactoryInterface`, `ServerRequestFactoryInterface`,
`StreamFactoryInterface`, `UploadedFileFactoryInterface` and `UriFactoryInterface` are answered
by [xtr-http-message](../xtr-http-message)'s `HttpFactory`, and `ResponseFactoryInterface` by
this package's `ResponseFactory` — so a response made through it is returnable as it is, like
the injected one.

Take those factories by their interfaces and the application decides what is behind them.
Reaching past them — `xtr_http_message.Response(...)`, `HttpFactory()` — in code that serves a
request gets you a message the framework cannot send, and is the one thing to avoid here. Those
classes are what a test, a worker or a console command builds, where there is no request being
served and no response to return.

Two more services cross between a message and the framework, for the times you hold the wrong
one:

| Service | Does |
|---|---|
| `HttpMessageFactoryInterface` | `await create_request(request)` and `create_response(response)`: the framework's own, as messages |
| `StarletteHttpFactoryInterface` | `await create_request(message, streamed=False)` and `await create_response(message, streamed=False)`: a message, as the framework's own |

A response that arrived from outside the application — one a worker built with
`xtr_http_message.Response(...)`, say — is sent by converting it with
`await StarletteHttpFactoryInterface.create_response(...)`; `streamed=True` sends the body in
chunks instead of whole. That conversion is for a message that *came from elsewhere*; a response
the application itself is answering with comes from the injected `ResponseFactoryInterface` or is
the injected `ResponseInterface`, and needs no conversion at all.

Neither direction alters what it is handed: where it cannot carry something across, it says so.
`create_response(response)` refuses a response that streams its body with
`StreamedResponseBodyError`, because reading that body would consume it and leave the response
with nothing to send — build the message from the content being streamed instead. It refuses a
response declaring a `Content-Range` with `RangedResponseBodyError` for the mirror reason: which
bytes of the file that header names is settled where the response is sent, so the message would
carry the whole file under a header saying it carries one part of it.
`StarletteHttpFactoryInterface.create_request(message)` refuses a cookie a `Cookie` header
cannot carry unchanged with `InvalidCookieError`, naming it: the cookies of a message are a
plain mapping nothing checked on the way in, and a value holding `;` would be read back as
further cookies of its own.

## Scoped services

A service registered `lifetime="scoped"` is built once per request and **released after the
response has been sent** — FastAPI's own timing for a dependency's cleanup. A service that
opens a unit of work per request therefore commits or rolls back once the caller has their
answer, and a generator factory's cleanup runs then. Put cleanup that must survive an error in
a `finally`: the engine throws a scope's error into the generator, so a commit that fails
raises there, and — with the logging listeners active — that failure is written to the log
against the request that caused it, like any other uncaught exception.

Nothing else is reset between requests. A service built for the application's life is shared
by every request, including the ones in flight at the same time, so the lifecycle clears no
state when a request begins or ends: a reset would wipe what a concurrent request is halfway
through. A service that must not outlive one request says so with `lifetime="scoped"`, and one
that remembers something per caller keys it by the caller instead of holding only the last.

## Listeners shipped

The bundle registers these; which ones depend on what is installed and active:

| Listener | Events | Active when | Does |
|---|---|---|---|
| `RequestIdListener` | `RequestEvent`, `ResponseEvent` | always | mints a `uuid4().hex` — or keeps a well-formed incoming id, where `trust_request_id` says to — puts it on `request.state.request_id`, binds it to the log context when logging is around, and echoes it on the response |
| `DisallowRobotsIndexingListener` | `ResponseEvent` | always | stamps `X-Robots-Tag: noindex` on every response, when the config turns it on |
| `LogUnitListener` | `RequestEvent`, `TerminateEvent` | logging bundle active | opens a [logging unit of work](../xtr-logging#units-of-work) per request and closes it once all was sent |
| `ErrorLoggingListener` | `ExceptionEvent` | logging bundle active | writes every uncaught exception to the request channel — `info` for a cancellation, an interrupt or an exit, `error` below a 500 status, `critical` otherwise — leaving the response to whoever answers it |
| `RateLimitHeadersListener` | `ResponseEvent` | rate limiter bundle active | writes the `X-RateLimit-*` headers of the [rate limit](#rate-limits) that speaks for the response, and makes it private |

The two logging listeners join only when the logging bundle is active, and open and close the
unit of work outside everything else so every record made while handling carries the request's
id. The request id settles right after the unit opens, for the same reason.

## Rate limits

With [xtr-rate-limiter](../xtr-rate-limiter) installed beside this package, a route, a router or
the whole application can be held to a limiter configured in that package's bundle.
`RateLimited` is one declaration, written as a decorator or wherever the framework takes a
dependency:

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

- **Install** — `uv add xtr-http-kernel`; install [xtr-logging](../xtr-logging) beside it for
  the listeners that write to a log, [xtr-console](../xtr-console) for the commands that report
  on the router, [xtr-rate-limiter](../xtr-rate-limiter) for the [rate limits](#rate-limits).
  None is needed to serve requests. The
  [HTTP message contract](../xtr-http-message-contracts) and
  [its implementation](../xtr-http-message) come with the package: the
  [messages](#the-request-and-the-response-as-messages) are part of what it does. So does the
  parser a submitted form with files in it is read with: building the request as a message
  asks the web framework for the form behind every multipart body, and the framework refuses
  outright where that parser is missing.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate* step below: it lists
  `HttpKernelBundle`. There is no config file, environment or ignore line to write; it prints the
  `setup(app, kernel)` step, which a recipe cannot make for you.
- **Activate** — `HttpKernelBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`, imported
  from `xtr_http_kernel.bundle`. Then call `setup(app, kernel)` where the application is built.
- **Brings along** — the [event dispatcher](../xtr-event-dispatcher) bundle always, because the
  lifecycle dispatches through it; the [logging](../xtr-logging), [console](../xtr-console) and
  [rate limiter](../xtr-rate-limiter) bundles whenever those packages are *installed* — they are
  required peers, pulled in and made active without being listed, and left out silently when the
  package is not installed. Listing is not what activates them; installing the package is. No
  bundle comes along for the messages: neither message package ships one, and this bundle
  registers their services itself.
- **Configure** — nothing is required: the zero-config path gives every request a fresh `uuid4`
  id under `X-Request-Id` — an inbound one is not trusted — no robots header, and the `request`
  log channel, and makes the request and the response of a request askable as
  [messages](#the-request-and-the-response-as-messages). A
  `<app>/config/http_kernel.py` `@configure` function returning an `HttpKernelConfig` changes
  that — see [Configure](#configure) and [Kernel / bundle](#kernel--bundle).
- **Environment** — nothing.
- **Ignore** — nothing.
- **Remove** — drop the `setup(app, kernel)` call, drop the `BUNDLES` entry, delete
  `<app>/config/http_kernel.py` if you wrote one, then `uv remove xtr-http-kernel`.
- **Check** — `debug:bundles` shows `http_kernel` as `listed` and `active`, `event_dispatcher`
  as `required`, and (when those packages are installed) `logging` and `console` as `required`;
  `debug:router` lists the application's routes.

## Configure

`HttpKernelConfig` is a frozen dataclass buildable with no arguments; every field has a
default:

| Field | Default | What it sets |
|---|---|---|
| `request_id_header` | `"X-Request-Id"` | the header the id is read from and echoed on; must be a non-empty HTTP token |
| `trust_request_id` | `False` | mint a fresh id every request; `True` keeps a well-formed incoming one |
| `disallow_search_indexing` | `False` | mark every response `X-Robots-Tag: noindex` |
| `log_channel` | `"request"` | the channel the error listener writes to |
| `middleware_priority` | `0` | where the lifecycle middleware sits among the contributed factories — highest outermost |
| `app` | `None` | the `"package.module:app"` string the router commands load the application from |

The constructor refuses values the lifecycle would silently misread: a `request_id_header` that
is not an HTTP token, an empty `log_channel`, or an `app` that is not exactly one module and one
attribute around a single `:`, each raise `InvalidArgumentError` — also a `ValueError`.

`trust_request_id` has one prerequisite: a proxy you control in front of the application, which
sets `request_id_header` itself and strips whatever the caller sent. Reached directly, the
caller chooses the id, so it can give two requests the same one — mixing their log records on
purpose, and making the one id an auditor follows useless. Without that proxy leave it off: the
minted id still travels on `request.state.request_id`, on every log record made while handling,
and out on the response, so a caller quoting the response's id names exactly one request. A
caller with its own trace id of a wider system sends it under a header of its own, which an
application reads like any other.

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
bundle is active — the router commands, plus the
[messages](#the-request-and-the-response-as-messages) and the factories behind them. It
requires the event dispatcher bundle outright, and
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

## Routes

A bundle ships its routes, and an application gets them served with no code in its entry point.
The application arranges them in its routes files, and `setup` adds the result.

### A bundle's routes

A route loader is a class with `load_routes()`, declared with `@as_route_loader`. It names the
*resource* an application imports its routes by:

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

The loader is built with no arguments while the kernel compiles, before any service exists, so
what it contributes is fixed by the code that ships it. A route a deployment turns off keeps
answering — its endpoint refuses — and an application that wants it gone leaves it out in a
routes file. Pass `prefixable=False` for routes a standard puts at a fixed place, such as a
`/.well-known/` document: no routes file may move them under a prefix. A loader is found like any
other declaration: in the application's scan, or in a module a bundle scans with
`services.load(...)`.

A `Route` carries a path, the endpoint the framework calls — its `Injected[...]` parameters
untouched — and the options handed to the framework as they are: `methods`,
`include_in_schema`, `tags`, `summary`, `status_code`, `response_model`. Its name is the key it
has in its `RouteCollection`. A mounted route validates, documents and is reached by
`url_path_for` exactly like the same function declared on a router.

### The application's routes files

A routes file is a function declared `@as_routes` in `<app>/config/routes/`, receiving a
`RoutingConfigurator`:

```python
from xtr_http_kernel.routing.decorator import as_routes
from xtr_http_kernel.routing.loader.configurator import RoutingConfigurator


@as_routes
def shop(routes: RoutingConfigurator) -> None:
    routes.import_("books").prefix("/shop").name_prefix("shop_")
    routes.add("shop_books_list", "/shop/catalogue")  # move one route by its name
    routes.add("home", "/").endpoint(home).methods("GET")


async def home() -> dict[str, str]:
    return {"page": "home"}
```

- `import_(resource)` brings in a resource's routes, arranged with `prefix`, `name_prefix` and
  `exclude(*names)`; `skip(resource)` serves none of them. A resource no routes file imports or
  skips is served at its own paths and names.
- `add(name, path)` defines a route. Under a name already in the table it replaces that route:
  without `.endpoint(...)` it moves the route and keeps the rest, with one it redefines it. Its
  options — `methods`, `priority`, `tags`, `summary`, `status_code`, `include_in_schema`,
  `response_model` — read like the `Route` fields.
- `collection(name_prefix)` groups routes under one path prefix and name prefix;
  `alias(name, target)` adds another name for a route, optionally `.deprecate(...)`d.
- Nothing reaches the table while the file runs: every call is applied when it returns, in the
  order written, so a route defined after an import replaces the imported one of that name.
  Each file starts from the resources as their loaders returned them.

A mistake is refused while the kernel compiles — so at `setup` — with an `InvalidArgumentError`
naming it: an unknown resource or route, a prefix on fixed routes, a new route with no endpoint,
two loaders claiming one resource. The kernel scans only packages, so `config/routes/` needs an
`__init__.py`; xtr-recipes creates it with the first routes file a recipe writes there.

### Collisions with the application's own routes

The application's own routes are never changed, and they come first. A contributed route sharing
a name with one the application declared, or one the application's routes would answer first —
the same method and path under any parameter names, a catch-all, a mount, or a router the
application included — fails `setup` with a `RouteConflictError` naming both; so do two
contributed routes answering the same method and path. To change a contributed route on purpose,
redefine it by its name in a routes file.

An alias is mounted under its own name, out of the API description, so `url_path_for` reaches it.
The table is also a service: `RouterInterface.get_route_collection()` returns a copy of what was
mounted, the same on every start of the application, for code that reads a route by name.

## Router commands

With a console bundle active, two commands read the application without serving it — every
route included, since `setup` added the contributed ones when the application was imported:

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
instead, inside its own lifespan so `setup`'s wrapper boots the kernel:

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
`override_services` **before** entering the lifespan, so every kernel booted while the block is
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
The overrides live on the application itself, so two tests serving one application must not
run at the same time: the block that exits last would restore what the other replaced.

## Errors

Everything this library raises derives from `HttpKernelError`, and carries what went wrong as
typed attributes rather than only a message. All of them are importable from `xtr_http_kernel`
itself, as well as from `xtr_http_kernel.exception`.

| Error | Raised when |
|---|---|
| `InvalidArgumentError` | an `HttpKernelConfig` field holds a value the lifecycle would misread; also a `ValueError` |
| `InvalidCookieError` | a request message carries a cookie a `Cookie` header cannot carry unchanged — a name that is not a token, or a value holding `;`, a control character or anything beyond visible ASCII; also a `ValueError` |
| `InvalidMiddlewarePriorityError` | a `http_kernel.middleware` tag's `priority` is not an integer |
| `InvalidRateLimitError` | a `RateLimited` takes fewer than one token, limits a router that already has routes, or its key function returns no string; also a `ValueError` |
| `RangedResponseBodyError` | a response being built into a message declares one range of the file it reads its body from, so the message would carry the whole file under a header saying otherwise |
| `ResponseAlreadyAMessageError` | the response being built into a message is the bridge's own, which already is a message: there is nothing to convert, and its body is awaited rather than read |
| `StreamedResponseBodyError` | a response being built into a message streams its body, which cannot be read without consuming it |
| `TooManyRequestsError` | a limiter refused the request — a 429 the framework answers, with `Retry-After` |
| `UnknownRateLimiterError` | a `RateLimited` names a limiter the application did not configure; also a `LookupError` |
| `UnsupportedConnectionError` | something asked for the request as a message while a WebSocket was being served |

The route table's errors live in `xtr_http_kernel.routing`, under `RoutingError` — itself an
`HttpKernelError`:

| Error | Raised when |
|---|---|
| `InvalidArgumentError` | a routes file names an unknown resource or route, prefixes fixed routes, defines a route with no endpoint, or is `async`; one file skips a resource another imports; two loaders claim one resource, or two resources no file arranges contribute one name; a loader needs arguments or has an `async` `load_routes`; an alias is refused. Also the library's own `InvalidArgumentError`, so a `ValueError` |
| `RouteConflictError` | `setup` finds a contributed route sharing a name with one the application declared, or answered first by one of the application's routes, or answering the same method and path as another contributed route |
| `RouteCircularReferenceError` | aliases lead back to a name they already passed |

## Layout

```
xtr_http_kernel/
├── setup.py                        setup(app, kernel), the one call an application makes
├── testing.py                      override_services, for a served application under test
├── bridge/                         the request and the response as HTTP messages, both ways
├── event/                          the five lifecycle events, one class per file
├── kernel_events.py                KernelEvents, the name each of them is dispatched under
├── event_listener/                 the listeners the bundle registers
├── request_lifecycle_middleware.py the middleware that dispatches the events
├── middleware_stack.py             the ordered chain a bundle contributes to
├── middleware_tag.py               MIDDLEWARE_TAG, the tag bundles agree on
├── rate_limiter/                   RateLimited, when xtr-rate-limiter is installed
├── routing/                        Route, RouteCollection, Router, the loaders and configurators
├── command/                        debug:router and router:match
├── exception/                      HttpKernelError, the root of everything this library raises
└── bundle/                         HttpKernelBundle and HttpKernelConfig
```

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-http-kernel`; run the commands below from there. The `python-xtr-http-kernel`
repository is a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync
uv run ruff check
uv run ruff format --check
uv run basedpyright
uv run ty check
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
