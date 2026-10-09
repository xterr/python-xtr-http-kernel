"""A binary file object that answers every read with part of what it holds."""

from __future__ import annotations

import io

from typing_extensions import override

__all__ = ["ShortReadFile"]


class ShortReadFile(io.BytesIO):
    """A buffer that hands over at most ``part`` bytes however much is asked for.

    A real one is a pipe, a socket or any file opened unbuffered: one read
    returns whatever has arrived rather than the whole of what was asked for,
    and only an empty answer says there is no more coming. Such a source has
    no cursor to move either, which is why this one reports itself unseekable.

    A test needs it to prove that a body is sent whole even when it arrives a
    little at a time, and it carries its own contract test.
    """

    def __init__(self, content: bytes, part: int) -> None:
        """Hold ``content``, handing over at most ``part`` bytes per read.

        Args:
            content: Everything the file holds.
            part: The most one read answers with.
        """
        super().__init__(content)
        self._part: int = part

    @override
    def seekable(self) -> bool:
        """Report that the cursor cannot be moved.

        Returns:
            Always ``False``.
        """
        return False

    @override
    def read(self, size: int | None = -1, /) -> bytes:
        """Return the next part of what the file holds, however much was asked for.

        Args:
            size: The most to read. A negative size — or none — asks for
                everything left, which a file object answers in full however
                it reads underneath; any other size is the source's to answer
                with as little as it has.

        Returns:
            Everything left where that was asked for; otherwise up to
            ``part`` bytes, and empty bytes once there are none left.
        """
        if size is None or size < 0:
            return super().read()

        return super().read(self._part)
