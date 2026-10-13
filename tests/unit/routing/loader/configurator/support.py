"""Endpoints and a ready-made resource the configurator tests share."""

from __future__ import annotations

from xtr_http_kernel.routing import Route, RouteCollection


async def endpoint() -> dict[str, str]:
    return {}


async def other_endpoint() -> dict[str, str]:
    return {}


def books() -> RouteCollection:
    routes = RouteCollection()
    routes.add("list", Route("/books", endpoint, methods=("GET",)))
    routes.add("show", Route("/books/{book_id}", endpoint, methods=("GET",)))
    return routes


def paths(collection: RouteCollection) -> dict[str, str]:
    return {name: route.path for name, route in collection}
