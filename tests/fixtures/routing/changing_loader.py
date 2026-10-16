"""A route reporting the mounted table, for the test that a later life serves the same one.

Routes are mounted once, in ``setup``; no later build changes what the
application serves, and the reporting endpoint reads what is mounted off the
application itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from starlette.requests import Request

from xtr_http_kernel._route_contexts import route_contexts
from xtr_http_kernel.routing.decorator import as_route_resource

if TYPE_CHECKING:
    from fastapi import APIRouter
    from starlette.applications import Starlette


@as_route_resource("changing")
def changing_routes(router: APIRouter) -> None:
    """Fill the router with the reported route and its reporter."""

    @router.get("/v1", name="changing")
    async def changing() -> dict[str, str]:
        return {}

    @router.get("/table", name="table")
    async def table(request: Request) -> dict[str, str]:
        app = cast("Starlette", request.app)
        reported: dict[str, str] = {}
        for view in route_contexts(app.routes):
            if view.name == "changing" and view.path is not None:
                reported[view.name] = view.path
        return reported
