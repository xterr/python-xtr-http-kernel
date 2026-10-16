"""The staging: what it refuses, and the native arrangement idioms it serves."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import APIRouter, FastAPI

from xtr_http_kernel._route_contexts import route_contexts
from xtr_http_kernel._staging import mount_routes
from xtr_http_kernel.routing import InvalidArgumentError, RouteConflictError, RouteRegistry

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from xtr_http_kernel.routing.decorator.as_routes import RoutesFile


async def _answer() -> dict[str, str]:
    return {}


def _filling(path: str, name: str, method: str = "GET") -> Callable[[APIRouter], None]:
    """Return a resource function adding one route."""

    def fill(router: APIRouter) -> None:
        router.add_api_route(path, _answer, methods=[method], name=name)

    return fill


def _include(*names: str) -> RoutesFile:
    """Return a routes file including the named resources at their own paths."""

    def file(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
        for name in names:
            app.include_router(resources[name])

    return file


def _names(app: FastAPI) -> list[str | None]:
    return [view.name for view in route_contexts(app.routes)]


def test_two_routes_of_one_resource_claiming_one_name_are_refused_while_staging() -> None:
    registry = RouteRegistry(
        resources=(
            ("books", _filling("/books", "books_list")),
            ("books", _filling("/other", "books_list")),
        )
    )

    with pytest.raises(InvalidArgumentError, match='named "books_list"'):
        mount_routes(FastAPI(), registry)


def test_a_file_asking_for_an_unknown_resource_is_refused_naming_it() -> None:
    registry = RouteRegistry(files=(_include("absent"),))

    with pytest.raises(InvalidArgumentError, match=r"'absent'.*nothing installed contributes"):
        mount_routes(FastAPI(), registry)


def test_including_one_resource_twice_is_refused_as_mounted_twice() -> None:
    registry = RouteRegistry(
        resources=(("books", _filling("/books", "books_list")),),
        files=(_include("books"), _include("books")),
    )

    with pytest.raises(RouteConflictError, match="mounted twice"):
        mount_routes(FastAPI(), registry)


def test_a_name_the_application_declared_is_refused() -> None:
    app = FastAPI()

    @app.get("/elsewhere", name="books_list")
    async def own() -> dict[str, str]:
        return {}

    registry = RouteRegistry(
        resources=(("books", _filling("/books", "books_list")),),
        files=(_include("books"),),
    )

    with pytest.raises(RouteConflictError, match="share the name"):
        mount_routes(app, registry)


def test_a_path_shape_the_application_answers_is_refused_under_any_parameter_name() -> None:
    app = FastAPI()

    @app.get("/books/{id}", name="my_book")
    async def own(id: str) -> dict[str, str]:  # noqa: A002 -- the parameter the path names
        return {"id": id}

    registry = RouteRegistry(
        resources=(("books", _filling("/books/{book_id}", "books_show")),),
        files=(_include("books"),),
    )

    with pytest.raises(RouteConflictError, match=r"answers GET /books/\{book_id\} first"):
        mount_routes(app, registry)


def test_two_contributed_routes_answering_one_method_and_shape_are_refused() -> None:
    registry = RouteRegistry(
        resources=(
            ("books", _filling("/books/{book_id}", "books_show")),
            ("shelf", _filling("/books/{id}", "shelf_show")),
        ),
        files=(_include("books", "shelf"),),
    )

    with pytest.raises(RouteConflictError, match="both answer GET"):
        mount_routes(FastAPI(), registry)


def test_excluding_one_route_is_a_filter_on_the_staged_router() -> None:
    def fill(router: APIRouter) -> None:
        router.add_api_route("/books", _answer, methods=["GET"], name="books_list")
        router.add_api_route("/secret", _answer, methods=["GET"], name="books_secret")

    def excluding(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
        books = resources["books"]
        books.routes = [
            route for route in books.routes if getattr(route, "name", None) != "books_secret"
        ]
        app.include_router(books)

    app = FastAPI()
    mount_routes(app, RouteRegistry(resources=(("books", fill),), files=(excluding,)))

    assert "books_list" in _names(app)
    assert "books_secret" not in _names(app)


def test_renaming_a_group_is_a_loop_over_the_staged_router() -> None:
    def renamed(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
        books = resources["books"]
        for route in books.routes:
            route.name = f"shop_{route.name}"  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]  # ty: ignore[unresolved-attribute]
        app.include_router(books, prefix="/shop")

    app = FastAPI()
    mount_routes(
        app,
        RouteRegistry(resources=(("books", _filling("/books", "books_list")),), files=(renamed,)),
    )

    assert "shop_books_list" in _names(app)
    assert app.url_path_for("shop_books_list") == "/shop/books"
