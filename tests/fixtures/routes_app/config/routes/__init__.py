"""The application's routes files: one module per set of routes it arranges.

Every function declared ``@as_routes`` here receives a ``RoutingConfigurator``
and arranges the routes bundles contribute — import a resource under a prefix
or a name prefix, leave routes out, redefine one by its name, skip a resource
— and adds the application's own. A resource no file here mentions is served
at its own paths and names. ``setup(app, kernel)`` adds the result to the
application; run ``<script> debug:router`` to see it.
"""

from __future__ import annotations

__all__: list[str] = []
