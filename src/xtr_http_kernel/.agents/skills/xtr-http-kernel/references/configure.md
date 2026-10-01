# HttpKernelConfig

A frozen dataclass buildable with no arguments; every field has a default. Import it from
`xtr_http_kernel.bundle` and return it from a `@configure` function in
`<app>/config/http_kernel.py`.

```python
from xtr_dependency_injection import configure

from xtr_http_kernel.bundle import HttpKernelConfig


@configure
def http_kernel() -> HttpKernelConfig:
    return HttpKernelConfig(disallow_search_indexing=True, app="app.web:app")
```

| Field | Default | What it sets |
| --- | --- | --- |
| `request_id_header` | `"X-Request-Id"` | the header the id is read from and echoed on; must be a non-empty HTTP token |
| `trust_request_id` | `True` | keep a well-formed incoming id; `False` mints a fresh one every request |
| `disallow_search_indexing` | `False` | mark every response `X-Robots-Tag: noindex` |
| `log_channel` | `"request"` | the logging channel the error listener writes to |
| `middleware_priority` | `0` | where the lifecycle middleware sits among the contributed factories, highest outermost |
| `app` | `None` | the `"package.module:app"` string the router commands load the application from |

## What the constructor refuses

Each raises `InvalidArgumentError`, which is also a `ValueError`:

- a `request_id_header` that is not an HTTP token (`"bad header"` with a space, or empty);
- an empty `log_channel`;
- an `app` that is not exactly one module and one attribute around a single `:`.

## log_channel

The bundle declares the default `request` channel on the logging config for you. An application
renaming it must declare the new channel in its **own** logging configuration: this bundle's
config resolves after logging's, so it cannot declare a name it does not yet know.

## app

Only the `debug:router` and `router:match` commands read it, and only when their `--app` option
is left out. A served application never needs it.
