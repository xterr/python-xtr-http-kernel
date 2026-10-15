"""Rate limits on routes, routers and whole applications, through the rate limiter bundle.

Needs xtr-rate-limiter, installed beside this package; importing this
package without it fails, which is why nothing else here imports it.
"""

from __future__ import annotations

from .rate_limited import RateLimited, RateLimitKey

__all__ = ["RateLimitKey", "RateLimited"]
