"""Rate limits on routes, routers and whole applications, through the rate limiter bundle.

Needs the ``rate-limiter`` extra, which brings xtr-rate-limiter; importing
this package without it fails, which is why nothing else here imports it.
"""

from __future__ import annotations

from .rate_limited import RateLimited, RateLimitKey

__all__ = ["RateLimitKey", "RateLimited"]
