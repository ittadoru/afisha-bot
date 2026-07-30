from typing import cast
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncEngine

from afishabot.core.database import EXPECTED_MIGRATION_HEAD, database_is_ready


async def test_database_requires_expected_migration_head() -> None:
    connection = AsyncMock()
    connection.scalar.return_value = EXPECTED_MIGRATION_HEAD
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=connection)
    context.__aexit__ = AsyncMock(return_value=False)
    engine = MagicMock()
    engine.connect.return_value = context

    assert await database_is_ready(cast(AsyncEngine, engine))


async def test_database_failure_closes_readiness() -> None:
    engine = MagicMock()
    engine.connect.side_effect = RuntimeError("unavailable")

    assert not await database_is_ready(cast(AsyncEngine, engine))


async def test_database_rejects_an_old_migration_head() -> None:
    connection = AsyncMock()
    connection.scalar.return_value = "old_revision"
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=connection)
    context.__aexit__ = AsyncMock(return_value=False)
    engine = MagicMock()
    engine.connect.return_value = context

    assert not await database_is_ready(cast(AsyncEngine, engine))
