# Routes

Everything about routing: what a package ships, what an application registers, and when each is
refused.

**Routing is never imported automatically.** A resource is served only when the application's
routes files include it; the routes file a package's recipe writes is that registration, and
deleting the file uninstalls the endpoints.

## Route resources (packages)

- `@as_route_resource("name")` from `xtr_http_kernel.routing.decorator`, on a plain function
  `(router: APIRouter) -> None` filling a router with the framework's own routes — the full
  native surface: `dependencies=`, `response_class`, `openapi_extra`, websockets.
- `setup` calls it once per resource, with no services and no side effects: what a package
  contributes is fixed by the code that ships it. An endpoint declares services with
  `Injected[...]`; a controller is a plain service, which the application replaces like any
  service (its own definition of the type outranks a bundle's).
- Several functions may fill one resource; two routes of a resource claiming one name are
  refused while staging.
- A route keeps the name it is declared with. Build URLs by name (`url_path_for`): a sender
  remembers a URL longer than a deployment remembers a path.
- Found in the application's scan, or in a module a bundle scans with `services.load(...)`.

## Routes files (application)

`@as_routes` functions in `<app>/config/routes/` — which needs an `__init__.py`, so the scan
finds it; recipes create it — called by `setup` with `(app, resources)` in scan order:

| Want | Native call |
|---|---|
| serve a resource | `app.include_router(resources["webhook"])` |
| move it under a prefix | `app.include_router(resources["webhook"], prefix="/hooks")` |
| skip it | do not include it — omission is the skip |
| leave one route out | `router.routes = [r for r in router.routes if r.name != "x"]` before including |
| rename the group | a loop setting `route.name` (and `route.operation_id`) before including; the framework has no name-prefixed include |
| replace a route | declare the application's own before `setup` — its routes come first — and filter the contributed one out |

- A resource is included by the first file including it; a second include of one is refused.
- Files apply immediately; an include copies the staged routes at call time.

## Refusals

All raised by `setup`:

| Error (`xtr_http_kernel.routing`) | When |
|---|---|
| `InvalidArgumentError` | a routes file asks for a resource nothing installed contributes; two routes of one resource claim one name; `@as_route_resource` on anything but a plain function, or with a blank name; an `async` routes file. Also the library's own `InvalidArgumentError`, so a `ValueError` |
| `RouteConflictError` | a contributed route shares a name with one the application declared; answers a method at the path shape — parameters by shape, not name — of one the application declared; two contributed routes answer one method and path shape; a resource is included twice |

The application's own routes come first and win: a catch-all of the application shadowing a
contributed route is the documented rule, not a refusal, and `router:match` answers who serves
what.

## Reading the routes

- `app.routes`, `app.url_path_for(name)` and the API description hold everything registered,
  right after `setup`.
- `debug:router` and `router:match` list and match the application like any other route.
