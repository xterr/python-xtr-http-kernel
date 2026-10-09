"""Driving a response the way a server does, and reading what went out."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from starlette.responses import Response
    from starlette.types import Message

__all__ = ["body_of", "sent"]


async def sent(response: Response, connection: str = "http") -> list[Message]:
    """Return every message ``response`` sent, in the order it sent them.

    Args:
        response: The response to drive.
        connection: What kind of connection it is answering.

    Returns:
        The messages the response handed to the server.
    """
    messages: list[Message] = []

    async def send(message: Message) -> None:
        messages.append(message)

    async def receive() -> Message:
        return {"type": "http.disconnect"}

    await response({"type": connection}, receive, send)

    return messages


def body_of(messages: list[Message]) -> bytes:
    """Return the body the sent ``messages`` amount to, chunks joined."""
    return b"".join(
        cast("bytes", message["body"])
        for message in messages
        if cast("str", message["type"]).endswith("response.body")
    )
