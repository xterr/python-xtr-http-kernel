"""The bridge between HTTP messages and the web framework serving the request.

A library that reads a request and fills in a response should not have to
know which web framework the application runs on; it takes the message
contract and nothing else. The framework, meanwhile, has already read the
request line, the headers, the body and the form. This is what joins the two:

- :class:`HttpMessageFactory` builds a request message out of the request the
  framework is serving — the body it cached, the form it parsed — and a
  response message out of a response it would send. Its ``serve`` builds the
  same request without reading it: a served request, whose body is one lazy
  stream, and which is what the lifecycle events carry.
- :class:`StarletteHttpFactory` goes the other way, for a message made
  somewhere else: it becomes a request the framework can route, or a
  response it can send.
- :class:`Response` is a response that is both at once, which is what lets an
  endpoint take one, write a status, a header and a body into it as a
  message, and return it as it is. :class:`ResponseFactory` makes them.

The bundle registers all four, so an endpoint or a per-request service asks
for ``ServerRequestInterface`` and ``ResponseInterface`` and receives them.
"""

from __future__ import annotations

from .http_message_factory import HttpMessageFactory
from .http_message_factory_interface import HttpMessageFactoryInterface
from .response import Response
from .response_factory import ResponseFactory
from .served_request import ServedRequest
from .starlette_http_factory import StarletteHttpFactory
from .starlette_http_factory_interface import StarletteHttpFactoryInterface

__all__ = [
    "HttpMessageFactory",
    "HttpMessageFactoryInterface",
    "Response",
    "ResponseFactory",
    "ServedRequest",
    "StarletteHttpFactory",
    "StarletteHttpFactoryInterface",
]
