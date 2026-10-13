"""Where the compiled kernel keeps the application's route table."""

from __future__ import annotations

from typing import Final

__all__ = ["ROUTE_TABLE_PARAMETER"]

#: The parameter holding the finished route table: the routing pass writes it
#: while the kernel compiles, ``setup()`` reads it right after, and the
#: ``Router`` service holds it.
ROUTE_TABLE_PARAMETER: Final = "http_kernel.route_table"
