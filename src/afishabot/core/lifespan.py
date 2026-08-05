from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI

from afishabot.core.config import Settings
from afishabot.core.database import create_database_engine
from afishabot.core.logging import configure_logging
from afishabot.core.metrics import NOMINATIM_AVAILABLE, REDIS_AVAILABLE
from afishabot.core.redis import create_redis_client, redis_is_available
from afishabot.modules.trust_safety.application.staff_admin import (
    bootstrap_first_admin,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = cast(Settings, app.state.settings)
    configure_logging(settings.log_level)
    settings.media_root.mkdir(mode=0o750, parents=True, exist_ok=True)

    engine = create_database_engine(settings.database_dsn())
    redis_client = create_redis_client(settings.redis_dsn())
    app.state.database_engine = engine
    app.state.redis_client = redis_client

    try:
        await bootstrap_first_admin(
            engine,
            login=settings.admin_login,
            password=settings.bootstrap_admin_password(),
        )
        REDIS_AVAILABLE.set(1 if await redis_is_available(redis_client) else 0)
        NOMINATIM_AVAILABLE.set(0)
        yield
    finally:
        await redis_client.aclose()
        await engine.dispose()
