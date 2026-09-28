"""Whether this framework release lets the commands see inside an included router.

A release that keeps a router included under a prefix as a wrapper, without
offering the effective view of the routes it holds, lists it as the one opaque
route the application holds. The tests that read a prefixed route out of a
listing only have something to read on the releases that show one.
"""

from __future__ import annotations

import pytest

from tests.fixtures.router_app.app import app
from xtr_http_kernel.command._route_contexts import route_contexts

PREFIXED_PATH = "/books/{isbn}"
"""The fixture application's one route reached through an included router."""

lists_included_routers = pytest.mark.skipif(
    all(view.path != PREFIXED_PATH for view in route_contexts(app.routes)),
    reason=(
        "this framework release neither flattens an included router into the application's "
        "routes nor offers the effective view of the routes it holds"
    ),
)
"""Runs the test only where a router included under a prefix reaches the listing."""
