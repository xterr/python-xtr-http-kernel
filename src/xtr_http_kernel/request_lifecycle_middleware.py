"""Dispatches the request lifecycle events around whatever application it wraps."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Protocol, cast, final, runtime_checkable

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from xtr_dependency_injection.runtime import shielded

from .bridge.served_connection import ServedConnection
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
    from xtr_http_message import ServerRequest

    from .bridge.http_message_factory_interface import HttpMessageFactoryInterface

__all__ = ["RequestLifecycleMiddleware"]

_SERVER_ERROR = 500

_CLEANUP_TIMEOUT: Final = 30.0
"""Seconds the finish and terminate listeners, and closing the connection, are each given.

They run to their end whatever cancels the request meanwhile — a disconnect,
a server's deadline — so a session is saved and a parsed form closed; the
deadline keeps a listener that never returns from holding the request forever.
"""

#: The message a server sends a whole file with, instead of body chunks.
_PATHSEND = "http.response.pathsend"


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
    finished before the last body chunk — or the file a server sends whole —
    leaves, and each announcement happens at most once however the request
    went: a response event whose listener raised is not dispatched again for
    the answer sent in its place.
    """

    __slots__ = (
        "_dispatcher",
        "_finished",
        "_request",
        "_response_dispatched",
        "_send",
        "_send_failure",
        "_state",
        "_status_sent",
    )

    def __init__(
        self,
        dispatcher: EventDispatcherInterface,
        request: ServerRequest,
        state: MutableMapping[str, object],
        send: Send,
    ) -> None:
        self._dispatcher = dispatcher
        self._request = request
        self._state = state
        self._send = send
        self._status_sent: int | None = None
        self._response_dispatched = False
        self._send_failure: BaseException | None = None
        self._finished = False

    @property
    def request(self) -> ServerRequest:
        return self._request

    @property
    def state(self) -> MutableMapping[str, object]:
        return self._state

    @property
    def response_started(self) -> bool:
        return self._status_sent is not None

    @property
    def status_sent(self) -> int:
        """The status the response started with, or 500 when it never started.

        What a layer outside the lifecycle did with it — answered 413 in its
        place, say — is that layer's, and not seen here.
        """
        return self._status_sent if self._status_sent is not None else _SERVER_ERROR

    def failed_sending(self, error: BaseException) -> bool:
        """Tell whether ``error`` is what the outer send raised, not what the application did."""
        return error is self._send_failure

    async def send(self, message: Message) -> None:
        message_type = cast("str", message["type"])
        if message_type == "http.response.start":
            if not self._response_dispatched:
                self._response_dispatched = True
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
            # Every start that leaves: an answer sent after a raising listener included.
            self._status_sent = cast("int", message["status"])
        elif message_type == _PATHSEND or (
            message_type == "http.response.body"
            and not cast("bool", message.get("more_body", False))
        ):
            await self.finish()
        try:
            await self._send(message)
        except BaseException as error:
            # Raised past the lifecycle — a layer outside it answering in the
            # application's place, a socket gone — and so not a failure of handling.
            self._send_failure = error
            raise

    async def finish(self) -> None:
        """Declare handling finished, the first time this is asked for.

        Its listeners run to their end even when the request is cancelled
        while they run: asked a second time, this does nothing.
        """
        if not self._finished:
            self._finished = True
            _ = await shielded(
                self._dispatcher.dispatch(FinishRequestEvent(self._request, self._state)),
                timeout=_CLEANUP_TIMEOUT,
            )


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
        message_factory=HttpMessageFactory(...),
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
    before the last body chunk leaves — or once handling ended any other way:
    a file sent whole, a client gone mid-stream, an unanswered failure — and
    :class:`~xtr_http_kernel.event.terminate_event.TerminateEvent` last, with
    the status that was sent. Each event at most once per request, and every
    one of them carries the request as a message — the served request, born
    connected to its connection, its body read only if a listener asks to read
    it — plus the per-request state bag the framework's own request wraps.

    A listener that does read the body drains the wire, so the application is
    handed a receive that replays the buffered bytes; a request no listener
    reads passes through untouched. A form the served request parsed is
    closed as the request leaves.

    A failure nobody answered propagates as it arrived: turning it into a
    response is the application's business, not this middleware's. A failure
    the server's ``send`` raised — a layer outside answering in the
    application's place, as a body limit answers 413, or a socket gone — is
    no failure of handling: it is announced to no exception listener, and
    propagates once the request finished. Only the
    lifespan of the application and its websockets pass through untouched —
    they are not requests.

    The finish and terminate listeners, and closing what the request opened,
    run to their end whatever cancels the request — each in a task of its own,
    in a copy of the request's context, so a listener cannot reset a context
    variable set earlier in the request — within :data:`_CLEANUP_TIMEOUT`
    seconds each; one still running then is cancelled with a ``TimeoutError``.

    When the dispatcher records per unit of work — it offers callable
    ``begin_unit`` and ``end_unit`` — each request is framed as one unit, so
    overlapping requests each trace only their own events.
    """

    __slots__ = ("_app", "_dispatcher", "_message_factory")

    def __init__(
        self,
        app: ASGIApp,
        *,
        dispatcher: EventDispatcherInterface,
        message_factory: HttpMessageFactoryInterface,
    ) -> None:
        """Wrap ``app``, announcing every request to ``dispatcher``'s listeners.

        Args:
            app: The application whose requests are announced.
            dispatcher: Where the lifecycle's events go.
            message_factory: Builds each request's served request message —
                the bridge's own factory when the container builds this, built by
                hand when nothing does.
        """
        self._app = app
        self._dispatcher = dispatcher
        self._message_factory = message_factory

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Carry one connection through, dispatching the lifecycle when it is a request."""
        if cast("str", scope["type"]) != "http":
            await self._app(scope, receive, send)
            return

        framework_request = Request(scope, receive)
        # The connection the request is served over, parked on the scope, so
        # the factory's serve builds the message over this very one.
        connection = ServedConnection(framework_request, self._message_factory)
        served = self._message_factory.serve(framework_request)
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
            await self._handle(scope, receive, lifecycle, connection)
        finally:
            try:
                try:
                    try:
                        # However handling ended: a file sent whole, a client gone
                        # mid-stream, a raising request listener.
                        await lifecycle.finish()
                    finally:
                        _ = await shielded(
                            self._dispatcher.dispatch(
                                TerminateEvent(served, state, lifecycle.status_sent)
                            ),
                            timeout=_CLEANUP_TIMEOUT,
                        )
                finally:
                    # In the request's own context: the unit it returns to is that context's.
                    if unit is not None:
                        unit.end_unit()
            finally:
                # A form a listener parsed through the served request is
                # closed even when no scoped service ever asked for one.
                await shielded(connection.close(), timeout=_CLEANUP_TIMEOUT)

    async def _handle(
        self,
        scope: Scope,
        receive: Receive,
        lifecycle: _Lifecycle,
        connection: ServedConnection,
    ) -> None:
        request_event = RequestEvent(lifecycle.request, lifecycle.state)
        _ = await self._dispatcher.dispatch(request_event)
        answer = request_event.response
        if answer is not None:
            await answer(scope, receive, lifecycle.send)
            return
        # A listener that read the served request's body drained the wire, so
        # the application is handed the buffered bytes back; otherwise the
        # original channel passes through untouched.
        app_receive = await connection.replay(receive)
        try:
            await self._app(scope, app_receive, lifecycle.send)
        except BaseException as error:
            if lifecycle.failed_sending(error):
                raise
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
            raise
