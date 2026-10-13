# Routes

Everything about the route table: what a bundle ships, what an application arranges, and when
each is refused.

## Route loaders

- `@as_route_loader(resource, *, prefixable=True)` from `xtr_http_kernel.routing.decorator`, on a
  class with `load_routes() -> RouteCollection`. A class without it, or a blank resource name, is
  refused where it is declared.
- The class is built with **no arguments** while the kernel compiles. It cannot ask for
  services or configuration: what it contributes is fixed. A route a deployment turns off keeps
  answering and its endpoint refuses; an application leaves it out with `exclude`.
- `prefixable=False` for routes a standard places, such as `/.well-known/...`: a routes file
  cannot move them under a prefix.
- Found in the application's scan, or in a module a bundle scans with `services.load(...)`.
  Two loaders claiming one resource fail the build.

## `Route` and `RouteCollection`

- `Route(path, endpoint, *, methods=(), include_in_schema=True, tags=(), summary=None,
  status_code=None, response_model=<unset>)` from `xtr_http_kernel.routing`. The path gets one
  leading slash; methods are upper-cased. Options go to the framework as they are, so the route
  behaves like the same function declared on a router.
- `RouteCollection.add(name, route, priority=0)` — a name added again replaces its route and
  moves it to the end. `all()` orders by priority, then declaration. Also `get`, `remove`,
  `add_prefix`, `add_name_prefix`, `add_collection`, `add_alias`, `copy`.

## Routes files

A function declared `@as_routes` in `<app>/config/routes/`, taking a `RoutingConfigurator`
(`xtr_http_kernel.routing.loader.configurator`):

| Call | Effect |
|---|---|
| `import_(resource)` | bring in a resource's routes; chain `.prefix(path)`, `.name_prefix(str)`, `.exclude(*names)` |
| `skip(resource)` | serve none of a resource's routes |
| `add(name, path)` | define a route; chain `.endpoint(fn)`, `.methods(...)`, `.priority(n)`, `.tags(...)`, `.summary(s)`, `.status_code(n)`, `.include_in_schema(include=bool)`, `.response_model(m)` |
| `collection(name_prefix)` | a group with its own `.prefix(path)`, `add`, `alias`, nested `collection` |
| `alias(name, target)` | another name for a route; chain `.deprecate(package, version, message)` |

- `add` under a name already in the table replaces that route. Without `.endpoint(...)` it moves
  it, keeping endpoint, methods and options; with one it redefines it. A new name needs an
  endpoint. Under an alias's name it moves or redefines the route the alias stands for.
- Nothing applies while the file runs: every call applies when it returns, in the order written.
  A route added after an import replaces the imported one of that name.
- Every file starts from the resources as their loaders returned them. Resources no file
  mentions come first, at their own paths; then each file, in scan order.
- A routes file is any `@as_routes` function the scan finds — a bundle scanning one with
  `services.load(...)` arranges the application's table too. Keep them in `<app>/config/routes/`.
- An alias is mounted under its own name, out of the API description, so `url_path_for` and
  `request.url_for` reach it.

## Refusals

All raised by `setup` — while the kernel compiles, or as the table is mounted:

| Error (`xtr_http_kernel.routing`) | When |
|---|---|
| `InvalidArgumentError` | unknown resource; `exclude` of a route the resource lacks; prefix on fixed routes; a new route with no endpoint; two loaders for one resource; a loader needing arguments or with an `async` `load_routes`; an `async` routes file; a resource one file skips and another imports; two resources no file arranges contributing one route name; an alias to itself or a bad deprecation message. Also the library's own `InvalidArgumentError`, so a `ValueError` |
| `RouteConflictError` | a contributed route shares a name with one the application declared, or a route the application declared — directly, through a router it included, a mount or a catch-all — would answer its method and path first; or two contributed routes answer the same method and path |
| `RouteCircularReferenceError` | aliases loop back (raised as the table is mounted) |

The application's own routes are never changed. To change a contributed one on purpose,
redefine it by its name in a routes file.

## Reading the table

- `app.routes`, `app.url_path_for(name)` and the API description hold every route right after
  `setup`.
- `RouterInterface` (`xtr_http_kernel.routing`) is a service whose `get_route_collection()`
  returns a copy of the table that was mounted — the same on every start of the application.
- `debug:router` and `router:match` list and match it like any other route.
