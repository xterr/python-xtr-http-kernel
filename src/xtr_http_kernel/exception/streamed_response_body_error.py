"""A response streams its body, so there is nothing a message could read."""

from __future__ import annotations

from .http_kernel_error import HttpKernelError

__all__ = ["StreamedResponseBodyError"]


class StreamedResponseBodyError(HttpKernelError):
    """The response being built into a message streams its body.

    A streamed body is an iterator the server drains once as it sends it:
    reading it here would consume it and leave the response with nothing to
    send, and handing over a message with an empty body instead would pass
    emptiness off as the answer. Build the message from the content the
    response was given, and stream that.

    Attributes:
        response: The kind of response whose body could not be read, as the
            name of its class.
    """

    response: str

    def __init__(self, response: str) -> None:
        """Record the kind of response whose body could not be read."""
        self.response = response
        super().__init__(
            f"A {response} cannot be built into a message: its body is a stream of "
            f"chunks, which cannot be read without consuming it and leaving the "
            f"response unsendable. Build the message from the content being streamed "
            f"instead.",
        )
