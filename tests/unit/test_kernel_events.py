"""Unit tests for :class:`xtr_http_kernel.KernelEvents`."""

from __future__ import annotations

import pytest
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from xtr_event_dispatcher import EventDispatcher
from xtr_event_dispatcher_contracts import Event, event_name_of

from xtr_http_kernel import (
    ExceptionEvent,
    FinishRequestEvent,
    KernelEvents,
    RequestEvent,
    ResponseEvent,
    TerminateEvent,
)

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    ("name", "event_class"),
    [
        (KernelEvents.REQUEST, RequestEvent),
        (KernelEvents.RESPONSE, ResponseEvent),
        (KernelEvents.EXCEPTION, ExceptionEvent),
        (KernelEvents.FINISH_REQUEST, FinishRequestEvent),
        (KernelEvents.TERMINATE, TerminateEvent),
    ],
)
def test_every_constant_is_the_name_its_event_is_dispatched_under(
    name: str,
    event_class: type[Event],
) -> None:
    assert name == event_name_of(event_class)


def test_the_five_names_are_distinct() -> None:
    names = {
        KernelEvents.REQUEST,
        KernelEvents.RESPONSE,
        KernelEvents.EXCEPTION,
        KernelEvents.FINISH_REQUEST,
        KernelEvents.TERMINATE,
    }

    assert len(names) == 5


async def test_a_listener_added_by_name_hears_the_event_dispatched_by_class(
    http_request: Request,
) -> None:
    dispatcher = EventDispatcher()
    heard: list[Event] = []

    def remember(event: Event) -> None:
        heard.append(event)

    dispatcher.add_listener(KernelEvents.REQUEST, remember)
    dispatcher.add_listener(KernelEvents.RESPONSE, remember)
    dispatcher.add_listener(KernelEvents.EXCEPTION, remember)
    dispatcher.add_listener(KernelEvents.FINISH_REQUEST, remember)
    dispatcher.add_listener(KernelEvents.TERMINATE, remember)

    for event in (
        RequestEvent(http_request),
        ResponseEvent(http_request, 200, MutableHeaders(raw=[])),
        ExceptionEvent(http_request, RuntimeError("boom")),
        FinishRequestEvent(http_request),
        TerminateEvent(http_request, 200),
    ):
        _ = await dispatcher.dispatch(event)

    assert [type(event) for event in heard] == [
        RequestEvent,
        ResponseEvent,
        ExceptionEvent,
        FinishRequestEvent,
        TerminateEvent,
    ]
