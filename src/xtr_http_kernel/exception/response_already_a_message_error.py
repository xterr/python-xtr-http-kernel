"""A response handed over for conversion already is a message of its own."""

from __future__ import annotations

from .http_kernel_error import HttpKernelError

__all__ = ["ResponseAlreadyAMessageError"]


class ResponseAlreadyAMessageError(HttpKernelError):
    """The response being built into a message already is one.

    The bridge's own response is both what the framework sends and a message
    in its own right, so converting it is asking to turn a message into the
    same message: there is nothing to do but read its body, which is awaited
    and so cannot be read here. Use the response as the message it already is —
    ``await response.get_body().get_contents()`` for its body — rather than
    handing it over to be converted.

    Attributes:
        response: The kind of response that already is a message, as the name
            of its class.
    """

    response: str

    def __init__(self, response: str) -> None:
        """Record the kind of response that already is a message."""
        self.response = response
        super().__init__(
            f'The response "{response}" already is a message; use it as one '
            f'(read its body with "await response.get_body().get_contents()") '
            f"instead of converting it.",
        )
