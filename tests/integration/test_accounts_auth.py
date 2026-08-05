import asyncio
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from afishabot.modules.accounts.application.auth import (
    confirm_age,
    credential_hash,
    load_session_profile,
    resolve_identity_and_issue_session,
    revoke_session,
)

pytestmark = pytest.mark.integration
AUTH_SECRET = b"integration-auth-secret-that-is-long-enough"


def required_database_url() -> str:
    value = os.environ.get("AFISHA_DATABASE_URL")
    if value is None:
        pytest.skip("AFISHA_DATABASE_URL is provided only by the VPS gate")
    return value


async def test_first_and_repeated_login_resolve_one_user() -> None:
    engine = create_async_engine(required_database_url())
    telegram_id = 9_000_000_001
    try:
        first, second = await asyncio.gather(
            resolve_identity_and_issue_session(
                engine,
                telegram_user_id=telegram_id,
                auth_secret=AUTH_SECRET,
            ),
            resolve_identity_and_issue_session(
                engine,
                telegram_user_id=telegram_id,
                auth_secret=AUTH_SECRET,
            ),
        )
        assert first.profile.user_id == second.profile.user_id
        assert first.profile.public_id == second.profile.public_id
        async with engine.connect() as connection:
            identity_count = await connection.scalar(
                text(
                    """
                    SELECT count(*) FROM accounts.telegram_identities
                    WHERE telegram_user_id = :telegram_id
                    """
                ),
                {"telegram_id": telegram_id},
            )
            stored_hash = await connection.scalar(
                text(
                    """
                    SELECT token_hash FROM accounts.sessions
                    WHERE user_id = :user_id AND revoked_at IS NULL
                    ORDER BY created_at LIMIT 1
                    """
                ),
                {"user_id": first.profile.user_id},
            )
        assert identity_count == 1
        assert stored_hash == credential_hash(AUTH_SECRET, first.token)
        assert stored_hash != first.token.encode()
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    DELETE FROM accounts.users
                    WHERE id = (
                        SELECT user_id FROM accounts.telegram_identities
                        WHERE telegram_user_id = :telegram_id
                    )
                    """
                ),
                {"telegram_id": telegram_id},
            )
        await engine.dispose()


async def test_age_confirmation_and_logout_follow_session_binding() -> None:
    engine = create_async_engine(required_database_url())
    session = await resolve_identity_and_issue_session(
        engine,
        telegram_user_id=9_000_000_002,
        auth_secret=AUTH_SECRET,
    )
    try:
        assert not session.profile.age_confirmed
        assert await confirm_age(
            engine,
            token=session.token,
            csrf_token="wrong",
            auth_secret=AUTH_SECRET,
        ) is None
        confirmed = await confirm_age(
            engine,
            token=session.token,
            csrf_token=session.csrf_token,
            auth_secret=AUTH_SECRET,
        )
        assert confirmed is not None and confirmed.age_confirmed
        assert await revoke_session(
            engine,
            token=session.token,
            csrf_token=session.csrf_token,
            auth_secret=AUTH_SECRET,
        )
        assert await load_session_profile(
            engine,
            token=session.token,
            auth_secret=AUTH_SECRET,
        ) is None
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM accounts.users WHERE id = :user_id"),
                {"user_id": session.profile.user_id},
            )
        await engine.dispose()
