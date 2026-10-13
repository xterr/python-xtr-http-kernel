"""The router: the application's route table, handed out as the caller's own copy."""

from __future__ import annotations

from xtr_http_kernel.routing import Route, RouteCollection, Router, RouterInterface


async def _endpoint() -> dict[str, str]:
    return {}


def test_the_router_returns_the_routes_it_holds() -> None:
    collection = RouteCollection()
    collection.add("home", Route("/", _endpoint))

    assert Router(collection).get_route_collection().all() == collection.all()


def test_changing_what_it_returned_changes_nothing_it_holds() -> None:
    collection = RouteCollection()
    collection.add("home", Route("/", _endpoint))
    router = Router(collection)

    router.get_route_collection().remove("home")

    assert list(router.get_route_collection().all()) == ["home"]


def test_the_router_is_a_router_interface() -> None:
    assert isinstance(Router(RouteCollection()), RouterInterface)
