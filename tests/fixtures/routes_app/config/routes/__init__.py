"""The application's routes files: one module per set of routes it arranges.

Every function declared ``@as_routes`` here receives the application and the
staged route resources — the routers the installed packages filled — and
includes the ones the application serves: at their own paths, under a prefix,
renamed, or with a route filtered out. A resource no file includes is not
served: routing is never imported automatically. ``setup(app, kernel)`` calls
the files in scan order; run ``<script> debug:router`` to see the result.
"""

from __future__ import annotations

__all__: list[str] = []
