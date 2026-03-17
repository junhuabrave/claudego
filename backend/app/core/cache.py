"""Redis cache client and FastAPI dependency.

Cache is optional — if REDIS_URL is not set the app starts normally and all
routes skip caching (passthrough). This prevents a hard startup failure when
Redis is not yet provisioned (e.g. staging bootstrap).

Usage in routes:
    redis: Redis | None = Depends(get_redis)
    if redis:
        cached = await redis.get(key)
        ...

Invalidation helpers (called by scheduler and mutation routes):
    await invalidate_news(redis)
    await invalidate_watchlist(redis, user_id)
    await invalidate_all_watchlists(redis)
"""

import logging

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None

NEWS_TTL = 60       # seconds
WATCHLIST_TTL = 30  # seconds


async def init_redis() -> None:
    global _redis
    if settings.redis_url:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        logger.info("Redis connected: %s", settings.redis_url)


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


async def get_redis() -> aioredis.Redis | None:
    """FastAPI dependency — returns the Redis client, or None if unconfigured."""
    return _redis


async def invalidate_news(redis: aioredis.Redis) -> None:
    """Delete all news cache entries. Called by scheduler after poll_news."""
    async for key in redis.scan_iter("news:*"):
        await redis.delete(key)


async def invalidate_watchlist(redis: aioredis.Redis, user_id: int) -> None:
    """Delete one user's watchlist cache. Called on watchlist add/remove."""
    await redis.delete(f"watchlist:{user_id}")


async def invalidate_all_watchlists(redis: aioredis.Redis) -> None:
    """Delete all watchlist entries. Called by scheduler after poll_quotes."""
    async for key in redis.scan_iter("watchlist:*"):
        await redis.delete(key)
