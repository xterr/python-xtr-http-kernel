# Rate limits

Needs the `rate-limiter` extra (`uv add "xtr-http-kernel[rate-limiter]"`) and limiters
configured in [xtr-rate-limiter](https://github.com/xterr/python-xtr-rate-limiter)'s bundle.
`RateLimited` names one of those limiters; everything else is where you put the declaration.

```python
from xtr_http_kernel.rate_limiter import RateLimited
```

## Where a declaration goes

```python
from fastapi import APIRouter, FastAPI, Request

app = FastAPI(dependencies=[RateLimited("global")])  # every route


@app.get("/books")
@RateLimited("api", expose_headers=True)  # BELOW the route decorator
async def list_books() -> list[Book]: ...


@app.post("/login", dependencies=[RateLimited("login", key=by_username, methods="post")])
async def login() -> None: ...


reports = RateLimited("reports")(APIRouter(prefix="/reports"))  # BEFORE its routes
app.include_router(admin, dependencies=[RateLimited("admin")])  # or when included
```

- A decorator must sit **below** the route decorator: the route reads the endpoint when it is
  declared.
- A router must be limited **before** routes are added, since each route copies its router's
  dependencies. A router that already has routes raises `InvalidRateLimitError`; give the limit
  to `include_router(..., dependencies=[...])` instead.
- The limit runs after routing and before the endpoint, in the framework's dependency order:
  the application's, the routers', then the route's.
- Two declarations naming one limiter both count. The published schema is untouched: the limit
  never appears as a parameter.

## Arguments

| Argument | Default | Meaning |
| --- | --- | --- |
| `limiter` | required | The name the limiter is configured under |
| `key` | `None` | What the request is counted under |
| `tokens` | `1` | Tokens one request consumes; below one raises `InvalidRateLimitError` |
| `methods` | `()` | The methods limited, every one when empty. One string or an iterable, case-insensitive; `GET` also limits `HEAD` |
| `expose_headers` | `False` | Report this limit in `X-RateLimit-*` headers |

### `key`

A string, or a function of the request returning a string, awaited when it returns an awaitable
(`RateLimitKey = str | Callable[[Request], str | Awaitable[str]]`). Anything but a string raises
`InvalidRateLimitError`.

```python
def by_username(request: Request) -> str:
    return request.headers.get("x-username", "anonymous")
```

With no `key`, a request counts under the client's address, the method and the route's **path
template**, so `/books/1` and `/books/2` share one count and varying a path parameter never
earns a fresh limit. Behind a proxy the address is the proxy's unless the server trusts its
forwarded headers (uvicorn's `--forwarded-allow-ips`).

## A refusal

- Answered `429 Too Many Requests` with `Retry-After`, raised as `TooManyRequestsError`. It is
  the framework's own HTTP exception, so an exception handler registered for it reshapes the
  body.
- A `RateLimitExceededEvent` naming the limiter and the key is dispatched first, when an event
  dispatcher is around.
- Limits consulted before the refusal keep their spend.
- A limiter the application never configured raises `UnknownRateLimiterError`, naming the ones
  it did.

## Headers

With `expose_headers=True` the response carries `X-RateLimit-Limit`, `X-RateLimit-Remaining` and
`X-RateLimit-Reset`, in calls rather than tokens, for the limit closest to refusing among those
exposing theirs. A refusing limit always speaks, and a limiter that keeps its state to itself
leaves the response without them. The response is made private, so a shared cache never serves
one caller's count to another.

## Limiting by hand

For a limit that only applies in some outcome, such as throttling logins only on failure,
inject the limiter by name like any other service:

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
