from redis.asyncio import Redis
from redis.asyncio import from_url

from config import settings

_client: Redis | None = None


def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    return _client


async def close() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None
