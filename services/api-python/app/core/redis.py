"""Redis/Valkey client for caching and pub/sub messaging."""

import redis.asyncio as redis

from app.core.config import settings

redis_client: redis.Redis | None = None


async def init_redis() -> redis.Redis:
    """Initialize and return the Redis client."""
    global redis_client
    redis_client = redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    return redis_client


async def close_redis() -> None:
    """Close the Redis connection."""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None


def get_redis() -> redis.Redis:
    """Return the global Redis client instance."""
    if redis_client is None:
        raise RuntimeError("Redis client not initialized. Call init_redis() first.")
    return redis_client
