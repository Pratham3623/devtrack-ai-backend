from typing import AsyncGenerator, Optional
import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import settings
from app.core.logging import logger

redis_client: Optional[Redis] = None


async def init_redis() -> None:
    global redis_client
    try:
        redis_client = aioredis.from_url(
            settings.REDIS_URI,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
        await redis_client.ping()
        logger.info("Successfully connected to Redis cluster.")
    except Exception as e:
        logger.error(f"Failed to connect to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT} - {str(e)}")
        redis_client = None


async def close_redis() -> None:
    global redis_client
    if redis_client is not None:
        await redis_client.close()
        logger.info("Closed Redis connection pool.")


async def get_redis() -> AsyncGenerator[Optional[Redis], None]:
    yield redis_client
