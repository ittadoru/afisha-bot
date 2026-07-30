from redis.asyncio import Redis


def create_redis_client(redis_url: str) -> Redis:
    return Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )


async def redis_is_available(client: Redis) -> bool:
    try:
        return bool(await client.ping())
    except Exception:
        return False
