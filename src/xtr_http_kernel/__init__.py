"""Requests turned into responses through events: a request lifecycle for web applications.

A web framework routes a request to the function that answers it. Everything
an application wants around that function — a request id on every response,
an uncaught exception written to the log with the request that caused it, a
header that keeps a page out of a search index — is not the endpoint's
business, and does not belong in each of them.

This library puts those between the framework and the endpoint as *events*:
a request announces itself, the response it produced announces itself, and
whoever listens contributes. Listeners come from the container, so they are
services like any other.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .exception import HttpKernelError

try:
    __version__ = version("xtr-http-kernel")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree with no installed metadata to read.
    __version__ = "0+unknown"

__all__ = ["HttpKernelError", "__version__"]
