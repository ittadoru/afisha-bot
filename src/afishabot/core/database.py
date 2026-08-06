from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

EXPECTED_MIGRATION_HEAD = "0023_interest_participation_waitlist"


def create_database_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, pool_pre_ping=True)


async def database_is_ready(engine: AsyncEngine) -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            revision = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
    except Exception:
        return False
    return revision == EXPECTED_MIGRATION_HEAD
