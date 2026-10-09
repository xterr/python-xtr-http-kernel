"""Makes the responses an endpoint can fill in and return as they are."""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_http_message_contracts.factory import ResponseFactoryInterface

from .response import Response

__all__ = ["ResponseFactory"]


@final
class ResponseFactory(ResponseFactoryInterface):
    """Builds responses that are both HTTP messages and what the framework sends.

    The response factory a served application registers, so that a library
    asking for one gets a response its endpoint can return without anything
    converting it.

    ```python
    response = factory.create_response(404)
    assert response.get_reason_phrase() == "Not Found"
    ```

    It holds no state, so one instance serves a whole application.
    """

    __slots__ = ()

    @override
    def create_response(self, code: int = 200, reason_phrase: str | None = None) -> Response:
        """Return a new response for ``code``.

        Args:
            code: The status code.
            reason_phrase: The phrase to go with ``code``. Left out, the
                recommended phrase for the code is filled in where there is
                one; given as an empty string, the response carries no phrase
                at all. That is the difference between asking for the usual
                phrase and asking for none.

        Returns:
            The response, with no header and no body yet.
        """
        return Response(code, reason_phrase)
