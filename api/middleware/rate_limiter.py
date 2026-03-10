"""
api/middleware/rate_limiter.py — Redis sliding-window rate limiter.

Key format: rate:{api_key_hash}:{minute_bucket}
Uses redis INCR with TTL=60s for each window.
"""

import time

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis

from api.dependencies import get_redis

# Requests per minute by tier
TIER_RATE_LIMITS: dict[str, int] = {
    "free": 60,
    "startup": 300,
    "growth": 1000,
    "enterprise": 5000,  # default for enterprise; overridable per account
}


async def check_rate_limit(
    request: Request,
    redis: Redis = Depends(get_redis),
) -> None:
    """FastAPI dependency that enforces per-key rate limits.

    Must be called AFTER auth middleware has set request.state.account
    and request.state.key_hash.

    Raises HTTPException(429) when the limit is exceeded.
    """
    account = getattr(request.state, "account", None)
    key_hash = getattr(request.state, "key_hash", None)

    if account is None or key_hash is None:
        return  # Auth not applied (e.g. health endpoint); skip rate limiting

    tier = account.tier or "free"
    limit = TIER_RATE_LIMITS.get(tier, TIER_RATE_LIMITS["free"])

    minute_bucket = int(time.time()) // 60
    redis_key = f"rate:{key_hash}:{minute_bucket}"

    current = await redis.incr(redis_key)
    if current == 1:
        await redis.expire(redis_key, 60)

    remaining = max(0, limit - current)
    reset_ts = (minute_bucket + 1) * 60

    # Always attach rate limit headers to the request state for the response
    request.state.rate_limit_limit = limit
    request.state.rate_limit_remaining = remaining
    request.state.rate_limit_reset = reset_ts

    if current > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error_code": "RATE_LIMITED",
                "message": f"Rate limit exceeded. Limit: {limit}/min.",
            },
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_ts),
                "Retry-After": str(reset_ts - int(time.time())),
            },
        )
