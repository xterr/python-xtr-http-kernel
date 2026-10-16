"""The kernel's route resources on a real application, from ``setup()`` on."""

from __future__ import annotations

from typing import cast

import pytest
from fastapi import APIRouter, FastAPI
from xtr_dependency_injection import Kernel

from tests.support.serving import serving
from xtr_http_kernel import setup
from xtr_http_kernel._route_contexts import route_contexts
from xtr_http_kernel.bundle import HttpKernelBundle
from xtr_http_kernel.routing import InvalidArgumentError, RouteConflictError

pytestmark = pytest.mark.anyio

_LOADERS = "tests.fixtures.routing.loaders"
_INCLUDED = "tests.fixtures.routing.included_routes"


def _set_up(app: FastAPI, *resources: str) -> FastAPI:
    setup(
        app,
        Kernel(
            "xtr_http_kernel.bundle",
            env="test",
            bundles={HttpKernelBundle: {"all": True}},
            resources=resources,
        ),
    )
    return app


def _names(app: FastAPI) -> list[str | None]:
    return [view.name for view in route_contexts(app.routes)]


async def test_a_resource_no_routes_file_includes_is_not_served() -> None:
    # Routing is never imported automatically: staging alone serves nothing.
    app = _set_up(FastAPI(), _LOADERS)

    async with serving(app) as client:
        answered = await client.get("/books")

    assert answered.status_code == 404
    assert "books_list" not in _names(app)


async def test_the_routes_file_that_includes_a_resource_is_what_serves_it() -> None:
    app = _set_up(FastAPI(), _LOADERS, _INCLUDED)

    async with serving(app) as client:
        books = await client.get("/books")
        metadata = await client.get("/.well-known/metadata")

    assert (books.status_code, books.json()) == (200, {"books": "all"})
    assert metadata.json() == {"issuer": "here"}


async def test_a_routes_file_arrangement_is_what_is_served() -> None:
    app = _set_up(FastAPI(), _LOADERS, "tests.fixtures.routing.arranged_routes")

    async with serving(app) as client:
        moved = await client.get("/shop/books")
        original = await client.get("/books")
        home = await client.get("/")

    assert moved.status_code == 200
    assert original.status_code == 404
    assert home.json() == {"home": "page"}
    assert app.url_path_for("shop_books_list") == "/shop/books"


async def test_an_endpoint_asking_for_a_value_of_the_container_gets_it() -> None:
    async with serving(
        _set_up(FastAPI(), "tests.fixtures.routing.status_loader", _INCLUDED)
    ) as client:
        answered = await client.get("/status")

    assert answered.json() == {"env": "test"}


async def test_a_mounted_route_validates_and_documents_like_a_declared_one() -> None:
    mounted = _set_up(FastAPI(), "tests.fixtures.routing.status_loader", _INCLUDED)
    declared = FastAPI()

    @declared.get("/pages/{number}", name="status_page")
    async def page(number: int) -> dict[str, int]:
        return {"page": number}

    async with serving(mounted) as client:
        refused = await client.get("/pages/abc")
    async with serving(declared) as client:
        expected = await client.get("/pages/abc")

    mounted_paths = cast("dict[str, object]", mounted.openapi()["paths"])
    assert refused.status_code == 422
    assert refused.json() == expected.json()
    assert mounted_paths["/pages/{number}"] == declared.openapi()["paths"]["/pages/{number}"]


async def test_starting_again_serves_the_same_routes_once() -> None:
    app = _set_up(FastAPI(), _LOADERS, _INCLUDED)

    async with serving(app):
        pass
    async with serving(app) as client:
        answered = await client.get("/books")

    assert answered.status_code == 200
    assert _names(app).count("books_list") == 1


def test_a_route_sharing_a_name_with_the_applications_own_is_refused_at_setup() -> None:
    app = FastAPI()

    @app.get("/elsewhere", name="books_list")
    async def own() -> dict[str, str]:
        return {}

    with pytest.raises(RouteConflictError, match=r'"books_list".*share the name'):
        _ = _set_up(app, _LOADERS, _INCLUDED)


def test_a_route_answering_the_same_method_and_path_is_refused_at_setup() -> None:
    app = FastAPI()

    @app.get("/books", name="my_books")
    async def own() -> dict[str, str]:
        return {}

    with pytest.raises(RouteConflictError, match="answers GET /books first"):
        _ = _set_up(app, _LOADERS, _INCLUDED)


async def test_another_method_at_the_same_path_is_not_a_conflict() -> None:
    app = FastAPI()

    @app.post("/books", name="add_book")
    async def own() -> dict[str, str]:
        return {"added": "yes"}

    async with serving(_set_up(app, _LOADERS, _INCLUDED)) as client:
        listed = await client.get("/books")
        added = await client.post("/books")

    assert (listed.status_code, added.json()) == (200, {"added": "yes"})


def test_a_route_of_a_router_the_application_included_is_checked_too() -> None:
    app = FastAPI()
    included = APIRouter(prefix="/api")

    @included.get("/books", name="api_books")
    async def own() -> dict[str, str]:
        return {}

    app.include_router(included)

    with pytest.raises(RouteConflictError, match="answers GET /api/books first"):
        _ = _set_up(app, _LOADERS, "tests.fixtures.routing.prefixed_routes")


async def test_a_catch_all_of_the_application_wins_by_order_and_is_not_refused() -> None:
    app = FastAPI()

    @app.get("/{path:path}", name="catch_all")
    async def catch_all(path: str) -> dict[str, str]:
        return {"path": path}

    async with serving(_set_up(app, _LOADERS, _INCLUDED)) as client:
        answered = await client.get("/books")

    # The application's own routes come first and win; router:match answers
    # who serves what — a shadow is a rule, not a refusal.
    assert answered.json() == {"path": "books"}


def test_the_same_path_under_another_parameter_name_is_refused() -> None:
    app = FastAPI()

    @app.get("/books/{id}", name="my_book")
    async def own(id: str) -> dict[str, str]:  # noqa: A002 -- the parameter the path names
        return {"id": id}

    with pytest.raises(RouteConflictError, match=r"answers GET /books/\{book_id\} first"):
        _ = _set_up(app, _LOADERS, _INCLUDED)


async def test_a_later_life_reports_the_routes_that_were_mounted() -> None:
    app = _set_up(FastAPI(), "tests.fixtures.routing.changing_loader", _INCLUDED)

    async with serving(app) as client:
        first = cast("dict[str, str]", (await client.get("/table")).json())
    async with serving(app) as client:
        second = cast("dict[str, str]", (await client.get("/table")).json())

    assert first == second == {"changing": "/v1"}


def test_two_contributed_routes_at_one_method_and_path_are_refused_at_setup() -> None:
    with pytest.raises(
        RouteConflictError, match="both answer GET /books, so this one is never reached"
    ):
        _ = _set_up(
            FastAPI(),
            _LOADERS,
            "tests.fixtures.routing.duplicate_path_loader",
            "tests.fixtures.routing.conflicting_paths_routes",
        )


def test_including_one_resource_twice_is_refused_at_setup() -> None:
    with pytest.raises(RouteConflictError, match="mounted twice"):
        _ = _set_up(FastAPI(), _LOADERS, "tests.fixtures.routing.twice_routes")


def test_a_routes_file_asking_for_an_unknown_resource_is_refused_at_setup() -> None:
    with pytest.raises(InvalidArgumentError, match="nothing installed contributes"):
        _ = _set_up(FastAPI(), "tests.fixtures.routing.missing_routes")
