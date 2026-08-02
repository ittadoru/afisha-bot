import os

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from afishabot.core.database import EXPECTED_MIGRATION_HEAD

pytestmark = pytest.mark.integration


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None:
        pytest.skip(f"{name} is provided only by the VPS integration gate")
    return value


async def test_postgis_and_migration_head() -> None:
    engine = create_async_engine(required_env("AFISHA_DATABASE_URL"))
    try:
        async with engine.connect() as connection:
            postgis = await connection.scalar(
                text("SELECT extname FROM pg_extension WHERE extname = 'postgis'")
            )
            head = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
        assert postgis == "postgis"
        assert head == EXPECTED_MIGRATION_HEAD
    finally:
        await engine.dispose()


async def test_redis_connection() -> None:
    client = Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
        required_env("AFISHA_REDIS_URL")
    )
    try:
        assert await client.ping()  # pyright: ignore[reportUnknownMemberType]
    finally:
        await client.aclose()
