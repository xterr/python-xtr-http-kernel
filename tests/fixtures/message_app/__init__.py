"""A fixture application whose routes ask for the request and the response as messages.

The two modules beside this one are what the kernel scans: a per-request
service that takes the request message through its constructor, and a
listener stamping each response so the tests can see the lifecycle still
reached it.
"""

from __future__ import annotations
