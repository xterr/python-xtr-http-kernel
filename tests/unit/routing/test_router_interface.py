"""What reads the route table: any object with ``get_route_collection()``."""

from __future__ import annotations

from xtr_http_kernel.routing import RouteCollection, RouterInterface


class _Table:
    def get_route_collection(self) -> RouteCollection:
        return RouteCollection()


def test_anything_reading_the_route_table_is_a_router_interface() -> None:
    assert isinstance(_Table(), RouterInterface)


def test_something_else_is_not() -> None:
    assert not isinstance(object(), RouterInterface)
