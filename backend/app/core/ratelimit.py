"""Dependency-free sliding-window rate limiter (per client IP + route bucket)."""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import settings
from app.core.errors import RateLimitError

_WINDOW = 60.0
_hits: dict[str, deque[float]] = defaultdict(deque)


def _client_key(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return fwd or (request.client.host if request.client else "unknown")


async def rate_limit(request: Request) -> None:
    key = f"{_client_key(request)}:{request.url.path}"
    now = time.monotonic()
    bucket = _hits[key]
    while bucket and now - bucket[0] > _WINDOW:
        bucket.popleft()
    limit = settings.rate_limit_per_minute
    if len(bucket) >= limit:
        retry = int(_WINDOW - (now - bucket[0])) + 1
        raise RateLimitError(
            f"Rate limit exceeded ({limit}/min). Retry in {retry}s.",
            details={"limit": limit, "window_seconds": _WINDOW, "retry_after": retry},
        )
    bucket.append(now)
