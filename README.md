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

> **Early days.** What ships today is the lifecycle's events, the bundle and the package's error
> base. The middleware that dispatches the events, `setup(app, kernel)` and the listeners that
> come with them land on top of this shape.

## Install

```sh
uv add xtr-http-kernel                      # the lifecycle and its bundle
uv add "xtr-http-kernel[logging]"           # + the listeners that log
uv add "xtr-http-kernel[console]"           # + the commands that report on the router
```

Requires Python 3.11+.

## Quick start

List the bundle; the application configures nothing else to get the defaults:

```python
# app/bundles.py
from xtr_http_kernel.bundle import HttpKernelBundle

BUNDLES = {HttpKernelBundle: {"all": True}}
```

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what
removing it undoes.

- **Install** — `uv add "xtr-http-kernel[logging,console]"`; `logging` brings the listeners that
  write to a log, `console` the commands that report on the router. Neither is needed to serve
  requests.
- **Activate** — `HttpKernelBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`, imported
  from `xtr_http_kernel.bundle`.
- **Brings along** — nothing yet.
- **Configure** — nothing to configure: `HttpKernelConfig` carries no fields, and the
  zero-config path is the whole of it. A `<app>/config/http_kernel.py` `@configure` function
  returning one is what changes that when it has fields — see
  [Kernel / bundle](#kernel--bundle).
- **Environment** — nothing.
- **Ignore** — nothing.
- **Remove** — drop the `BUNDLES` entry, delete `<app>/config/http_kernel.py` if you wrote one,
  then `uv remove xtr-http-kernel`.
- **Check** — `debug:bundles` shows `http_kernel` as `listed` and `active`.

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
    return HttpKernelConfig()
```

## The lifecycle

Every request goes through the same events, and a listener joins wherever it has something to
contribute:

| Event | When | What a listener may do |
|---|---|---|
| `RequestEvent` | it arrived, nothing has looked at it | read it, or `set_response(...)` to answer instead of the application |
| `ResponseEvent` | a response is about to start | assign `status_code`, change `headers` in place |
| `ExceptionEvent` | handling raised, nothing was sent | read `exception`, or `set_response(...)` to answer with it |
| `FinishRequestEvent` | handling finished — **on every path** | put away what the request set up |
| `TerminateEvent` | everything was sent | work worth doing once the caller has their answer |

`RequestEvent.set_response` and `ExceptionEvent.set_response` stop the event: the listeners after
them do not run, because the request has been dealt with. A response is streamed, so
`ResponseEvent` carries no body — only the head, which has not left yet.

Events are keyed by the qualified name of their class, so a listener declared on a typed
parameter and one registered under the matching `KernelEvents` constant are the same
registration:

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

## Errors

Everything this library raises derives from `HttpKernelError`, and carries what went wrong as
typed attributes rather than only a message.

## Layout

```
xtr_http_kernel/
├── event/            the five lifecycle events, one class per file
├── kernel_events.py  KernelEvents, the name each of them is dispatched under
├── exception/        HttpKernelError, the root of everything this library raises
└── bundle/           HttpKernelBundle for xtr-dependency-injection
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
