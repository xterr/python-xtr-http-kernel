"""Dispatches the request lifecycle events around whatever application it wraps."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast, final, runtime_checkable

from starlette.datastructures import MutableHeaders
from starlette.requests import Request

from .event import (
    ExceptionEvent,
    FinishRequestEvent,
    RequestEvent,
    ResponseEvent,
    TerminateEvent,
)

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send
    from xtr_event_dispatcher_contracts import EventDispatcherInterface

__all__ = ["RequestLifecycleMiddleware"]

_SERVER_ERROR = 500


@runtime_checkable
class _UnitScopedDispatcher(Protocol):
    """What a dispatcher recording per unit of work offers on top of dispatching."""

    def begin_unit(self) -> None: ...

    def end_unit(self) -> None: ...


@final
class _Lifecycle:
    """One request's passage: a ``send`` that dispatches around what leaves.

    The middleware and the responses a listener answers with all send through
    this one wrapper, so the sending rules live in one place: the response
    start is announced (and adjusted) before it leaves, handling is declared
    finished before the last body chunk leaves, and each announcement happens
    at most once however the request went.
    """

    __slots__ = ("_dispatcher", "_finished", "_request", "_send", "_status_sent")

    def __init__(self, dispatcher: EventDispatcherInterface, request: Request, send: Send) -> None:
        self._dispatcher = dispatcher
        self._request = request
        self._send = send
        self._status_sent: int | None = None
        self._finished = False

    @property
    def request(self) -> Request:
        return self._request

    @property
    def response_started(self) -> bool:
        return self._status_sent is not None

    @property
    def status_sent(self) -> int:
        """The status that left, or 500 when the response never started."""
        return self._status_sent if self._status_sent is not None else _SERVER_ERROR

    async def send(self, message: Message) -> None:
        message_type = cast("str", message["type"])
        if message_type == "http.response.start" and self._status_sent is None:
            event = ResponseEvent(
                self._request,
                cast("int", message["status"]),
                # The message's own header list, so what a listener writes is
                # what leaves.
                MutableHeaders(scope=message),
            )
            _ = await self._dispatcher.dispatch(event)
            message["status"] = event.status_code
            self._status_sent = event.status_code
        elif message_type == "http.response.body" and not cast(
            "bool", message.get("more_body", False)
        ):
            await self.finish()
        await self._send(message)

    async def finish(self) -> None:
        """Declare handling finished, the first time this is asked for."""
        if not self._finished:
            self._finished = True
            _ = await self._dispatcher.dispatch(FinishRequestEvent(self._request))


@final
class RequestLifecycleMiddleware:
    """Announces each moment of a request's life to whoever listens.

    Sits between the server and the application as plain middleware — built
    from an application and a dispatcher, nothing else — so a framework
    registers it the way it registers any other:

    ```python
    app.add_middleware(RequestLifecycleMiddleware, dispatcher=dispatcher)
    ```

    Every request then goes through the same sequence, whatever becomes of
    it: :class:`~xtr_http_kernel.event.request_event.RequestEvent` before the
    application sees it (a listener answering there skips the application),
    :class:`~xtr_http_kernel.event.response_event.ResponseEvent` before the
    response start leaves,
    :class:`~xtr_http_kernel.event.exception_event.ExceptionEvent` when
    handling raised (a listener answering there swallows the failure, unless
    the response already started),
    :class:`~xtr_http_kernel.event.finish_request_event.FinishRequestEvent`
    before the last body chunk leaves — or before an unanswered failure
    propagates — and
    :class:`~xtr_http_kernel.event.terminate_event.TerminateEvent` last, with
    the status that was sent. Each event at most once per request.

    A failure nobody answered propagates as it arrived: turning it into a
    response is the application's business, not this middleware's. Only the
    lifespan of the application and its websockets pass through untouched —
    they are not requests.

    When the dispatcher records per unit of work — it offers callable
    ``begin_unit`` and ``end_unit`` — each request is framed as one unit, so
    overlapping requests each trace only their own events.
    """

    __slots__ = ("_app", "_dispatcher")

    def __init__(self, app: ASGIApp, *, dispatcher: EventDispatcherInterface) -> None:
        """Wrap ``app``, announcing every request to ``dispatcher``'s listeners."""
        self._app = app
        self._dispatcher = dispatcher

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Carry one connection through, dispatching the lifecycle when it is a request."""
        if cast("str", scope["type"]) != "http":
            await self._app(scope, receive, send)
            return

        lifecycle = _Lifecycle(self._dispatcher, Request(scope, receive), send)
        unit = (
            self._dispatcher
            if isinstance(self._dispatcher, _UnitScopedDispatcher)
            and callable(self._dispatcher.begin_unit)
            and callable(self._dispatcher.end_unit)
            else None
        )
        if unit is not None:
            unit.begin_unit()
        try:
            await self._handle(scope, receive, lifecycle)
        finally:
            try:
                _ = await self._dispatcher.dispatch(
                    TerminateEvent(lifecycle.request, lifecycle.status_sent)
                )
            finally:
                if unit is not None:
                    unit.end_unit()

    async def _handle(self, scope: Scope, receive: Receive, lifecycle: _Lifecycle) -> None:
        request_event = RequestEvent(lifecycle.request)
        _ = await self._dispatcher.dispatch(request_event)
        answer = request_event.response
        if answer is not None:
            await answer(scope, receive, lifecycle.send)
            return
        try:
            await self._app(scope, receive, lifecycle.send)
        except BaseException as error:
            exception_event = ExceptionEvent(lifecycle.request, error)
            _ = await self._dispatcher.dispatch(exception_event)
            answer = exception_event.response
            # Only a failure is answered: a cancellation, an interrupt or an exit goes on
            # as it arrived, or timeouts, cancelled tasks and shutdowns would stop working.
            if (
                answer is not None
                and not lifecycle.response_started
                and isinstance(error, Exception)
            ):
                await answer(scope, receive, lifecycle.send)
                return
            await lifecycle.finish()
            raise
