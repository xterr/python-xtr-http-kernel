"""A response declares one range of its body, so reading the file would say more."""

from __future__ import annotations

from .http_kernel_error import HttpKernelError

__all__ = ["RangedResponseBodyError"]


class RangedResponseBodyError(HttpKernelError):
    """The response being built into a message declares a ``Content-Range``.

    The header says the body is one part of the file; which part that is, and
    the reading of it, belong to where the response is sent. A message built
    here would carry the whole file under a header saying it carries a part of
    it — the two halves of the message contradicting each other, which is
    worse than either alone. Build the message from the range being sent
    instead.

    Attributes:
        response: The kind of response whose body could not be read, as the
            name of its class.
        content_range: The range the response declares, as the header carries
            it.
    """

    response: str
    content_range: str

    def __init__(self, response: str, content_range: str) -> None:
        """Record the kind of response that was refused and the range it declares."""
        self.response = response
        self.content_range = content_range
        super().__init__(
            f'A {response} declaring Content-Range cannot be built into a message: "'
            f'{content_range}" says the body is one part of the file, and which bytes '
            f"that is is settled where the response is sent, not here — so the message "
            f"would carry the whole file under a header saying otherwise. Build the "
            f"message from the range being sent instead.",
        )
