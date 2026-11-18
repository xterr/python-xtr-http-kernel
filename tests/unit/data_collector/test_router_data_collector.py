from __future__ import annotations

from tests.support.profiling import profiled
from xtr_http_kernel.data_collector.router_data_collector import RouterDataCollector


def test_the_route_noted_on_the_state_is_kept() -> None:
    route: dict[str, object] = {"matched": True, "name": "show_book", "path_params": {}}

    data = RouterDataCollector().collect(profiled(state={"_profiler.route": route}))

    assert data == {**route, "redirect": None}


def test_where_a_redirect_pointed_is_kept() -> None:
    data = RouterDataCollector().collect(
        profiled(status_code=302, response_headers={"location": "/login"})
    )

    assert data == {"matched": False, "path_params": {}, "redirect": "/login"}
    assert RouterDataCollector().name == "router"
