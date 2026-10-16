"""The framework's own request and response, as HTTP messages."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Final, cast, final

from starlette.datastructures import UploadFile
from typing_extensions import override

# Read at runtime: the container fills these constructor parameters from the
# annotations, and the upload outcome is a value this module names.
from xtr_http_message import ServerRequest
from xtr_http_message_contracts import UploadError
from xtr_http_message_contracts.factory import (
    ResponseFactoryInterface,  # noqa: TC002 — read at runtime, as above.
    ServerRequestFactoryInterface,  # noqa: TC002 — read at runtime, as above.
    StreamFactoryInterface,  # noqa: TC002 — read at runtime, as above.
    UploadedFileFactoryInterface,  # noqa: TC002 — read at runtime, as above.
    UriFactoryInterface,  # noqa: TC002 — read at runtime, as above.
)

from xtr_http_kernel.exception import (
    RangedResponseBodyError,
    ResponseAlreadyAMessageError,
    StreamedResponseBodyError,
)

from ._headers import grouped_headers
from ._media_types import is_form as _is_form
from ._media_types import is_json as _is_json
from ._media_types import media_type_of as _media_type
from ._scope_uri import scope_uri
from ._server_params import _DEFAULT_PROTOCOL, _server_params
from .http_message_factory_interface import HttpMessageFactoryInterface
from .response import Response as BridgeResponse
from .served_connection import ServedConnection, served_connection_of

if TYPE_CHECKING:
    from collections.abc import Mapping

    from starlette.datastructures import FormData
    from starlette.requests import Request
    from starlette.responses import Response
    from xtr_http_message_contracts import (
        ResponseInterface,
        ServerRequestInterface,
        StreamInterface,
        UploadedFileInterface,
    )

__all__ = ["HttpMessageFactory"]

_CONTENT_RANGE: Final = "content-range"


@final
class HttpMessageFactory(HttpMessageFactoryInterface):
    """Builds HTTP messages out of what the framework already holds.

    Every part of the message comes from the request object the framework is
    serving, so nothing is read off the wire twice: the body is the one the
    framework cached, and the form is the one it parsed — or the one this
    factory parses, which the framework then finds cached in its turn.

    ```python
    message = await factory.create_request(request)
    assert message.get_query_params()["page"] == "2"
    ```

    The six parts a request message carries beyond a plain one are filled in
    as the framework reports them:

    | On the message | Comes from |
    |---|---|
    | environment parameters | the connection's own entries |
    | attributes | the parameters the matched route named |
    | cookies | the cookies the framework read |
    | query parameters | the framework's own, handed over as they are |
    | parsed body | the form, or a JSON object, or nothing |
    | uploaded files | the files in the form, each wrapped where it lies |

    The query parameters and the form are the framework's own objects, not
    copies of them, so asking one of them for every value of a repeated name
    still works.
    """

    __slots__ = (
        "_response_factory",
        "_server_request_factory",
        "_stream_factory",
        "_uploaded_file_factory",
        "_uri_factory",
    )

    def __init__(
        self,
        server_request_factory: ServerRequestFactoryInterface,
        stream_factory: StreamFactoryInterface,
        uploaded_file_factory: UploadedFileFactoryInterface,
        response_factory: ResponseFactoryInterface,
        uri_factory: UriFactoryInterface,
    ) -> None:
        """Build messages through the factories the application registered.

        Five rather than one: a message is assembled from five kinds of part,
        and taking each factory by its own interface leaves an application
        free to replace one of them. Nothing is discovered — what is not
        passed is not available.

        Args:
            server_request_factory: Builds the request message.
            stream_factory: Builds every body, and wraps every uploaded file.
            uploaded_file_factory: Builds the uploaded files.
            response_factory: Builds the response message.
            uri_factory: Builds the URI of the request.
        """
        self._server_request_factory = server_request_factory
        self._stream_factory = stream_factory
        self._uploaded_file_factory = uploaded_file_factory
        self._response_factory = response_factory
        self._uri_factory = uri_factory

    @override
    def serve(self, request: Request) -> ServerRequest:
        """Return ``request`` as a served request, reading nothing off the wire.

        The head is built from the connection alone and the body is left
        lazy — the message is born connected to a
        :class:`~xtr_http_kernel.bridge.served_connection.ServedConnection`
        — so the lifecycle can hand a request message to its listeners
        without any of them costing a request its stream.

        The connection the message reads through parks itself on the
        request's scope, and the message it serves is answered from there
        however many times this is called: one request, one message.

        Args:
            request: The request the framework is serving.

        Returns:
            The same request, as a message nothing has read the body of.
        """
        connection = served_connection_of(request.scope)
        if connection is None:
            connection = ServedConnection(request, self)

        message = connection.message
        if message is None:
            message = connection.park(
                ServerRequest.over(
                    request.method,
                    scope_uri(self._uri_factory, request.scope),
                    source=connection,
                    headers=grouped_headers(request.headers.raw),
                    server_params=_server_params(request.scope),
                    cookies=request.cookies,
                    query=request.query_params,
                    protocol_version=cast(
                        "str", request.scope.get("http_version", _DEFAULT_PROTOCOL)
                    ),
                )
            )

        return message

    @override
    async def create_request(self, request: Request) -> ServerRequestInterface:
        """Return ``request`` as a server request message.

        A header the message grammar refuses is left out rather than failing
        the request: the framework let it through, and a message is no place
        to re-litigate that.

        Args:
            request: The request the framework is serving.

        Returns:
            The same request, as a message.
        """
        scope = request.scope
        message = self._server_request_factory.create_server_request(
            request.method,
            scope_uri(self._uri_factory, scope),
            _server_params(scope),
        )

        for name, values in grouped_headers(request.headers.raw).items():
            try:
                message = message.with_header(name, values)
            except ValueError:
                continue

        media_type = _media_type(request.headers.get("content-type", ""))
        form = await request.form() if _is_form(media_type) else None
        message = (
            message.with_body(await self._request_body(request, form))
            .with_uploaded_files(self._uploaded_files(form))
            .with_cookie_params(request.cookies)
            .with_query_params(request.query_params)
            .with_parsed_body(await self._parsed_body(request, media_type, form))
            .with_protocol_version(cast("str", scope.get("http_version", _DEFAULT_PROTOCOL)))
        )

        path_params = cast("Mapping[str, object]", scope.get("path_params", {}))
        for name, value in path_params.items():
            message = message.with_attribute(name, value)

        return message

    @override
    def create_response(self, response: Response) -> ResponseInterface:
        """Return ``response`` as a response message.

        The reason phrase is the one recommended for the status code: the
        framework writes no phrase of its own, and the server fills one in.

        Args:
            response: The response the framework would send.

        Returns:
            The same response, as a message.

        Raises:
            ResponseAlreadyAMessageError: When the response is the bridge's own,
                which already is a message: there is nothing to convert, and its
                body is awaited rather than read here.
            RangedResponseBodyError: When the response declares one range of
                the file it reads its body from: the message would carry the
                whole file under a header saying it carries a part of it.
            StreamedResponseBodyError: When the response streams its body: it
                could only be read by consuming it, which would leave the
                response with nothing to send.
        """
        if isinstance(response, BridgeResponse):
            raise ResponseAlreadyAMessageError(type(response).__name__)

        message = self._response_factory.create_response(response.status_code).with_body(
            self._response_body(response)
        )

        for name, values in grouped_headers(response.raw_headers).items():
            try:
                message = message.with_header(name, values)
            except ValueError:
                continue

        return message

    async def _request_body(self, request: Request, form: FormData | None) -> StreamInterface:
        """Return the body of a request message, empty where a form consumed it.

        A submitted form is the body, read and taken apart; what is left on
        the wire is nothing, so the message's body is the empty stream and
        the fields are its parsed body instead.
        """
        if form is not None:
            return self._stream_factory.create_stream()

        return self._stream_factory.create_stream(await request.body())

    def _response_body(self, response: Response) -> StreamInterface:
        """Return the body of a response message, read from wherever it sits.

        Raises:
            RangedResponseBodyError: When the body is a file the response
                declares one range of.
            StreamedResponseBodyError: When there is no body to read, only
                chunks the server would drain.
        """
        rendered = cast("bytes | memoryview | None", getattr(response, "body", None))
        if rendered is not None:
            return self._stream_factory.create_stream(bytes(rendered))

        path = cast("object", getattr(response, "path", None))
        if isinstance(path, (str, os.PathLike)):
            declared = response.headers.get(_CONTENT_RANGE)
            if declared is not None:
                raise RangedResponseBodyError(type(response).__name__, declared)

            return self._stream_factory.create_stream_from_file(os.fsdecode(path), "rb")

        raise StreamedResponseBodyError(type(response).__name__)

    async def _parsed_body(
        self,
        request: Request,
        media_type: str,
        form: FormData | None,
    ) -> object | None:
        """Return what parsing the body yielded, or nothing where it yielded no structure.

        A submitted form is handed over as the framework's own object. A JSON
        body is the object it describes; a JSON body that is not an object —
        a list, a number, a string — and one that is not JSON at all read as
        nothing, since neither says what fields were submitted.
        """
        if form is not None:
            return form

        if not _is_json(media_type):
            return None

        try:
            parsed = cast("object", await request.json())
        except ValueError:
            return None

        return cast("Mapping[str, object]", parsed) if isinstance(parsed, dict) else None

    def _uploaded_files(self, form: FormData | None) -> Mapping[str, object]:
        """Return the files in ``form``, under the names they were submitted with.

        A name submitted more than once — a field taking several files — maps
        to every file sent under it, in order; a name submitted once maps to
        its file.
        """
        if form is None:
            return {}

        gathered: dict[str, object] = {}
        for name, value in form.multi_items():
            if not isinstance(value, UploadFile):
                continue
            one = self._uploaded_file(value)
            if name not in gathered:
                gathered[name] = one
            else:
                held = gathered[name]
                gathered[name] = (*held, one) if isinstance(held, tuple) else (held, one)

        return gathered

    def _uploaded_file(self, upload: UploadFile) -> UploadedFileInterface:
        """Return one submitted file, wrapped where it lies rather than copied.

        A field submitted with no file at all is still reported, carrying the
        outcome that says so: whether a file was offered is often the
        question.
        """
        if upload.filename is None or upload.filename == "":
            return self._uploaded_file_factory.create_uploaded_file(
                self._stream_factory.create_stream(), 0, UploadError.NO_FILE
            )

        return self._uploaded_file_factory.create_uploaded_file(
            self._stream_factory.create_stream_from_resource(upload.file),
            upload.size,
            UploadError.OK,
            upload.filename,
            upload.content_type,
        )
