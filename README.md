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

> **Early days.** What ships today is the bundle and the package's error base. The lifecycle
> events, the middleware that dispatches them, `setup(app, kernel)` and the listeners that come
> with them land on top of this shape.

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

## Errors

Everything this library raises derives from `HttpKernelError`, and carries what went wrong as
typed attributes rather than only a message.

## Layout

```
xtr_http_kernel/
├── exception/   HttpKernelError, the root of everything this library raises
└── bundle/      HttpKernelBundle for xtr-dependency-injection
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
