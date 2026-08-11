from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from afishabot.modules.accounts.application.profiles import ProfileView, create_report


@pytest.mark.asyncio
async def test_photo_report_snapshots_avatar_and_background_assets() -> None:
    avatar_id = uuid4()
    background_id = uuid4()
    connection = SimpleNamespace(execute=AsyncMock())

    @asynccontextmanager
    async def begin() -> AsyncGenerator[SimpleNamespace]:
        yield connection

    engine = cast(AsyncEngine, SimpleNamespace(begin=begin))
    subject = ProfileView(
        user_id=uuid4(),
        public_id="12345678",
        display_name="Амина",
        bio=None,
        selected_city_id=None,
        city_name=None,
        avatar_asset_id=avatar_id,
        background_asset_id=background_id,
        version=3,
        next_name_change_at=datetime.now(UTC),
        organizer_status="trusted",
        successful_events=4,
        upcoming_count=1,
        completed_count=2,
    )

    await create_report(
        engine,
        reporter_id=uuid4(),
        subject=subject,
        reason="photo",
        comment=None,
    )

    parameters = connection.execute.await_args_list[0].args[1]
    assert parameters["avatar"] == avatar_id
    assert parameters["background"] == background_id
    assert connection.execute.await_count == 4
