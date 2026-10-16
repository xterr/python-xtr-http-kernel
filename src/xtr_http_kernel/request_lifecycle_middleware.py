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
    from collections.abc import MutableMapping

    from starlette.types import ASGIApp, Message, Receive, Scope, Send
    from xtr_event_dispatcher_contracts import EventDispatcherInterface

    from .bridge.http_message_factory_interface import HttpMessageFactoryInterface
    from .bridge.served_request import ServedRequest

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

    __slots__ = ("_dispatcher", "_finished", "_request", "_send", "_state", "_status_sent")

    def __init__(
        self,
        dispatcher: EventDispatcherInterface,
        request: ServedRequest,
        state: MutableMapping[str, object],
        send: Send,
    ) -> None:
        self._dispatcher = dispatcher
        self._request = request
        self._state = state
        self._send = send
        self._status_sent: int | None = None
        self._finished = False

    @property
    def request(self) -> ServedRequest:
        return self._request

    @property
    def state(self) -> MutableMapping[str, object]:
        return self._state

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
                self._state,
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
            _ = await self._dispatcher.dispatch(FinishRequestEvent(self._request, self._state))


@final
class RequestLifecycleMiddleware:
    """Announces each moment of a request's life to whoever listens.

    Sits between the server and the application as plain middleware — built
    from an application, a dispatcher and the bridge's message factory,
    nothing else — so a framework registers it the way it registers any
    other:

    ```python
    app.add_middleware(
        RequestLifecycleMiddleware,
        dispatcher=dispatcher,
        messages=HttpMessageFactory(...),
    )
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
    the status that was sent. Each event at most once per request, and every
    one of them carries the request as a message — the served request, built
    from the connection alone, its body read only if a listener asks to read
    it — plus the per-request state bag the framework's own request wraps.

    A listener that does read the body drains the wire, so the application is
    handed a receive that replays the buffered bytes; a request no listener
    reads passes through untouched. A form the served request parsed is
    closed as the request leaves.

    A failure nobody answered propagates as it arrived: turning it into a
    response is the application's business, not this middleware's. Only the
    lifespan of the application and its websockets pass through untouched —
    they are not requests.

    When the dispatcher records per unit of work — it offers callable
    ``begin_unit`` and ``end_unit`` — each request is framed as one unit, so
    overlapping requests each trace only their own events.
    """

    __slots__ = ("_app", "_dispatcher", "_messages")

    def __init__(
        self,
        app: ASGIApp,
        *,
        dispatcher: EventDispatcherInterface,
        messages: HttpMessageFactoryInterface,
    ) -> None:
        """Wrap ``app``, announcing every request to ``dispatcher``'s listeners.

        Args:
            app: The application whose requests are announced.
            dispatcher: Where the lifecycle's events go.
            messages: Builds each request's served request message — the
                bridge's own factory when the container builds this, built by
                hand when nothing does.
        """
        self._app = app
        self._dispatcher = dispatcher
        self._messages = messages

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Carry one connection through, dispatching the lifecycle when it is a request."""
        if cast("str", scope["type"]) != "http":
            await self._app(scope, receive, send)
            return

        served = self._messages.serve(Request(scope, receive))
        # The same bag the framework's own request wraps, created here so a
        # listener and the framework write one state between them.
        state = cast("MutableMapping[str, object]", scope.setdefault("state", {}))
        lifecycle = _Lifecycle(self._dispatcher, served, state, send)
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
                try:
                    _ = await self._dispatcher.dispatch(
                        TerminateEvent(served, state, lifecycle.status_sent)
                    )
                finally:
                    if unit is not None:
                        unit.end_unit()
            finally:
                # A form a listener parsed through the served request is
                # closed even when no scoped service ever asked for one.
                await served.close()

    async def _handle(self, scope: Scope, receive: Receive, lifecycle: _Lifecycle) -> None:
        request_event = RequestEvent(lifecycle.request, lifecycle.state)
        _ = await self._dispatcher.dispatch(request_event)
        answer = request_event.response
        if answer is not None:
            await answer(scope, receive, lifecycle.send)
            return
        # A listener that read the served request's body drained the wire, so
        # the application is handed the buffered bytes back; otherwise the
        # original channel passes through untouched.
        app_receive = await lifecycle.request.replay(receive)
        try:
            await self._app(scope, app_receive, lifecycle.send)
        except BaseException as error:
            exception_event = ExceptionEvent(lifecycle.request, lifecycle.state, error)
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
