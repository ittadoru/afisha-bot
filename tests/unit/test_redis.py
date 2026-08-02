from typing import cast
from unittest.mock import AsyncMock, MagicMock

from redis.asyncio import Redis

from afishabot.core.redis import redis_is_available


async def test_redis_is_only_an_availability_signal() -> None:
    client = MagicMock()
    client.ping = AsyncMock(return_value=True)

    assert await redis_is_available(cast(Redis, client))


async def test_redis_failure_is_safe() -> None:
    client = MagicMock()
    client.ping = AsyncMock(side_effect=RuntimeError("unavailable"))

    assert not await redis_is_available(cast(Redis, client))
