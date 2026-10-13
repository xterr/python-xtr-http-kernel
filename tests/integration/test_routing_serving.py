"""The kernel's route table on a real application, from ``setup()`` on."""

from __future__ import annotations

from typing import cast

import pytest
from fastapi import APIRouter, FastAPI
from xtr_dependency_injection import Kernel

from tests.fixtures.routing.status_loader import page
from tests.support.serving import serving
from xtr_http_kernel import setup
from xtr_http_kernel._route_contexts import route_contexts
from xtr_http_kernel.bundle import HttpKernelBundle
from xtr_http_kernel.routing import RouteConflictError

pytestmark = pytest.mark.anyio

_LOADERS = "tests.fixtures.routing.loaders"
_STATUS = "tests.fixtures.routing.status_loader"


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


def test_after_setup_the_application_holds_every_route_without_starting() -> None:
    app = _set_up(FastAPI(), _LOADERS, "tests.fixtures.routing.arranged_routes")

    assert {"shop_books_list", "metadata", "home"} <= set(_names(app))
    assert app.url_path_for("shop_books_list") == "/shop/books"


async def test_contributed_routes_are_served_with_no_code_in_the_entry_point() -> None:
    async with serving(_set_up(FastAPI(), _LOADERS)) as client:
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


async def test_an_endpoint_asking_for_a_service_gets_it() -> None:
    async with serving(_set_up(FastAPI(), _STATUS)) as client:
        answered = await client.get("/status")

    assert answered.json() == {"routes": 2}


async def test_a_mounted_route_validates_and_documents_like_a_declared_one() -> None:
    mounted = _set_up(FastAPI(), _STATUS)
    declared = FastAPI()
    _ = declared.get("/pages/{number}", name="status_page")(page)

    async with serving(mounted) as client:
        refused = await client.get("/pages/abc")
    async with serving(declared) as client:
        expected = await client.get("/pages/abc")

    mounted_paths = cast("dict[str, object]", mounted.openapi()["paths"])
    assert refused.status_code == 422
    assert refused.json() == expected.json()
    assert mounted_paths["/pages/{number}"] == declared.openapi()["paths"]["/pages/{number}"]


async def test_starting_again_serves_the_same_routes_once() -> None:
    app = _set_up(FastAPI(), _LOADERS)

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
        _ = _set_up(app, _LOADERS)


def test_a_route_answering_the_same_method_and_path_is_refused_at_setup() -> None:
    app = FastAPI()

    @app.get("/books", name="my_books")
    async def own() -> dict[str, str]:
        return {}

    with pytest.raises(RouteConflictError, match="answers GET /books first"):
        _ = _set_up(app, _LOADERS)


async def test_another_method_at_the_same_path_is_not_a_conflict() -> None:
    app = FastAPI()

    @app.post("/books", name="add_book")
    async def own() -> dict[str, str]:
        return {"added": "yes"}

    async with serving(_set_up(app, _LOADERS)) as client:
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


def test_a_catch_all_route_of_the_application_shadowing_a_contributed_one_is_refused() -> None:
    app = FastAPI()

    @app.get("/{path:path}", name="catch_all")
    async def own(path: str) -> dict[str, str]:
        return {"path": path}

    with pytest.raises(RouteConflictError, match=r'"catch_all".*answers GET'):
        _ = _set_up(app, _LOADERS)


def test_the_same_path_under_another_parameter_name_is_refused() -> None:
    app = FastAPI()

    @app.get("/books/{id}", name="my_book")
    async def own(id: str) -> dict[str, str]:  # noqa: A002 -- the parameter the path names
        return {"id": id}

    with pytest.raises(RouteConflictError, match=r"answers GET /books/\{book_id\} first"):
        _ = _set_up(app, _LOADERS)


def test_an_alias_is_reached_by_its_name() -> None:
    app = _set_up(FastAPI(), _LOADERS, "tests.fixtures.routing.aliased_routes")

    assert app.url_path_for("catalogue") == "/books"
    assert "catalogue" not in str(cast("object", app.openapi()["paths"]))


async def test_a_later_life_reports_the_routes_that_were_mounted() -> None:
    app = _set_up(FastAPI(), "tests.fixtures.routing.changing_loader")

    async with serving(app) as client:
        first = cast("dict[str, str]", (await client.get("/table")).json())
    async with serving(app) as client:
        second = cast("dict[str, str]", (await client.get("/table")).json())

    assert first == second == {"changing": "/v1"}


def test_two_contributed_routes_at_one_method_and_path_are_refused_at_setup() -> None:
    with pytest.raises(
        RouteConflictError, match="both answer GET /books, so this one is never reached"
    ):
        _ = _set_up(FastAPI(), _LOADERS, "tests.fixtures.routing.duplicate_path_loader")
