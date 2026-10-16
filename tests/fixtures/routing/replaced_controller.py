"""An application replacing the controller a route injects."""

from __future__ import annotations

from xtr_dependency_injection import as_service

from tests.support.bundles import Tick, TickController


@as_service
def replaced_tick_controller() -> TickController:
    """Register the controller under the application's own definition.

    The application outranks the bundle that registered it, so the endpoint
    injects this controller — and answers with the token it was built with.
    """
    return TickController(Tick("replaced"))
