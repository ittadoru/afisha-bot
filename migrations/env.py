from asyncio import run
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from afishabot.core.config import Settings
from afishabot.modules.accounts.infrastructure.metadata import (
    metadata as accounts_metadata,
)
from afishabot.modules.communication.infrastructure.metadata import (
    metadata as communication_metadata,
)
from afishabot.modules.discovery.infrastructure.metadata import (
    metadata as discovery_metadata,
)
from afishabot.modules.events.infrastructure.metadata import metadata as events_metadata
from afishabot.modules.media.infrastructure.metadata import metadata as media_metadata
from afishabot.modules.reputation.infrastructure.metadata import (
    metadata as reputation_metadata,
)
from afishabot.modules.trust_safety.infrastructure.metadata import (
    metadata as trust_safety_metadata,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This migration-only aggregation is the documented exception to module isolation.
target_metadata = [
    accounts_metadata,
    discovery_metadata,
    events_metadata,
    communication_metadata,
    trust_safety_metadata,
    reputation_metadata,
    media_metadata,
]


def run_migrations_offline() -> None:
    context.configure(
        url=Settings().database_dsn(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = Settings().database_dsn()
    engine = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
