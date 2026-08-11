# ruff: noqa: RUF001 -- generated Russian pseudonym is intentional.

import hashlib
import hmac
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.ext.asyncio import AsyncEngine

SESSION_TTL = timedelta(hours=24)
AGE_RULE_VERSION = "14-plus-v1"


@dataclass(frozen=True, slots=True)
class AccountProfile:
    user_id: UUID
    public_id: str
    display_name: str
    bio: str | None
    selected_city_id: UUID | None
    age_confirmed: bool


@dataclass(frozen=True, slots=True)
class IssuedSession:
    token: str
    csrf_token: str
    expires_at: datetime
    profile: AccountProfile
    created: bool


def credential_hash(secret: bytes, value: str) -> bytes:
    return hmac.new(secret, value.encode(), hashlib.sha256).digest()


async def resolve_identity_and_issue_session(
    engine: AsyncEngine,
    *,
    telegram_user_id: int,
    auth_secret: bytes,
) -> IssuedSession:
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + SESSION_TTL

    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT pg_advisory_xact_lock(:identity_key)"),
            {"identity_key": telegram_user_id},
        )
        row = (
            await connection.execute(
                text(
                    """
                    SELECT u.id, u.accepted_age_rule_at, p.public_id,
                           p.display_name, p.bio, p.selected_city_id
                    FROM accounts.telegram_identities AS ti
                    JOIN accounts.users AS u ON u.id = ti.user_id
                    JOIN accounts.profiles AS p ON p.user_id = u.id
                    WHERE ti.telegram_user_id = :telegram_user_id
                    FOR UPDATE OF ti, u, p
                    """
                ),
                {"telegram_user_id": telegram_user_id},
            )
        ).mappings().one_or_none()
        created = row is None
        if row is None:
            user_id = uuid4()
            public_id = await _reserve_public_id(connection)
            display_name = f"Гость {secrets.randbelow(10_000):04d}"
            await connection.execute(
                text("INSERT INTO accounts.users (id) VALUES (:user_id)"),
                {"user_id": user_id},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO accounts.telegram_identities
                        (user_id, telegram_user_id)
                    VALUES (:user_id, :telegram_user_id)
                    """
                ),
                {"user_id": user_id, "telegram_user_id": telegram_user_id},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO accounts.profiles
                        (user_id, public_id, display_name)
                    VALUES (:user_id, :public_id, :display_name)
                    """
                ),
                {
                    "user_id": user_id,
                    "public_id": public_id,
                    "display_name": display_name,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO reputation.organizer_profiles (user_id) VALUES (:user_id)"
                ),
                {"user_id": user_id},
            )
            profile = AccountProfile(
                user_id=user_id,
                public_id=public_id,
                display_name=display_name,
                bio=None,
                selected_city_id=None,
                age_confirmed=False,
            )
        else:
            await connection.execute(
                text(
                    """
                    UPDATE accounts.telegram_identities
                    SET last_authenticated_at = now()
                    WHERE telegram_user_id = :telegram_user_id
                    """
                ),
                {"telegram_user_id": telegram_user_id},
            )
            profile = _profile_from_row(row)

        await connection.execute(
            text(
                """
                INSERT INTO accounts.sessions
                    (id, user_id, token_hash, csrf_token_hash, expires_at)
                VALUES (:id, :user_id, :token_hash, :csrf_token_hash, :expires_at)
                """
            ),
            {
                "id": uuid4(),
                "user_id": profile.user_id,
                "token_hash": credential_hash(auth_secret, token),
                "csrf_token_hash": credential_hash(auth_secret, csrf_token),
                "expires_at": expires_at,
            },
        )
    return IssuedSession(token, csrf_token, expires_at, profile, created)


async def load_session_profile(
    engine: AsyncEngine,
    *,
    token: str,
    auth_secret: bytes,
) -> AccountProfile | None:
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    """
                    SELECT u.id, u.accepted_age_rule_at, p.public_id,
                           p.display_name, p.bio, p.selected_city_id
                    FROM accounts.sessions AS s
                    JOIN accounts.users AS u ON u.id = s.user_id
                    JOIN accounts.profiles AS p ON p.user_id = u.id
                    WHERE s.token_hash = :token_hash
                      AND s.revoked_at IS NULL
                      AND s.expires_at > now()
                      AND u.status = 'active'
                    """
                ),
                {"token_hash": credential_hash(auth_secret, token)},
            )
        ).mappings().one_or_none()
    return None if row is None else _profile_from_row(row)


async def rotate_session_csrf(
    engine: AsyncEngine,
    *,
    token: str,
    auth_secret: bytes,
) -> tuple[AccountProfile, str] | None:
    csrf_token = secrets.token_urlsafe(32)
    async with engine.begin() as connection:
        row = (
            await connection.execute(
                text(
                    """
                    UPDATE accounts.sessions AS s
                    SET csrf_token_hash = :csrf_hash
                    FROM accounts.users AS u, accounts.profiles AS p
                    WHERE s.user_id = u.id
                      AND p.user_id = u.id
                      AND s.token_hash = :token_hash
                      AND s.revoked_at IS NULL
                      AND s.expires_at > now()
                      AND u.status = 'active'
                    RETURNING u.id, u.accepted_age_rule_at, p.public_id,
                              p.display_name, p.bio, p.selected_city_id
                    """
                ),
                {
                    "csrf_hash": credential_hash(auth_secret, csrf_token),
                    "token_hash": credential_hash(auth_secret, token),
                },
            )
        ).mappings().one_or_none()
    if row is None:
        return None
    return _profile_from_row(row), csrf_token


async def confirm_age(
    engine: AsyncEngine,
    *,
    token: str,
    csrf_token: str,
    auth_secret: bytes,
) -> AccountProfile | None:
    async with engine.begin() as connection:
        user_id = (
            await connection.execute(
                text(
                    """
                    SELECT u.id
                    FROM accounts.users AS u
                    JOIN accounts.sessions AS s ON s.user_id = u.id
                    WHERE s.token_hash = :token_hash
                      AND s.csrf_token_hash = :csrf_hash
                      AND s.revoked_at IS NULL
                      AND s.expires_at > now()
                      AND u.status = 'active'
                    FOR UPDATE OF u, s
                    """
                ),
                {
                    "token_hash": credential_hash(auth_secret, token),
                    "csrf_hash": credential_hash(auth_secret, csrf_token),
                },
            )
        ).scalar_one_or_none()
        if user_id is None:
            return None
        accepted_at = datetime.now(UTC)
        await connection.execute(
            text(
                """
                INSERT INTO accounts.age_acceptances
                    (id, user_id, rule_version, accepted_at)
                VALUES (:id, :user_id, :rule_version, :accepted_at)
                ON CONFLICT (user_id, rule_version) DO NOTHING
                """
            ),
            {
                "id": uuid4(),
                "user_id": user_id,
                "rule_version": AGE_RULE_VERSION,
                "accepted_at": accepted_at,
            },
        )
        await connection.execute(
            text(
                """
                UPDATE accounts.users
                SET accepted_age_rule_version = :rule_version,
                    accepted_age_rule_at = COALESCE(accepted_age_rule_at, :accepted_at),
                    updated_at = now()
                WHERE id = :user_id
                """
            ),
            {
                "user_id": user_id,
                "rule_version": AGE_RULE_VERSION,
                "accepted_at": accepted_at,
            },
        )
    return await load_session_profile(engine, token=token, auth_secret=auth_secret)


async def complete_onboarding(
    engine: AsyncEngine,
    *,
    token: str,
    csrf_token: str,
    auth_secret: bytes,
    selected_city_id: UUID,
    expected_profile_version: int,
) -> AccountProfile | None:
    """Atomically save the mandatory age acknowledgement and home city."""
    async with engine.begin() as connection:
        row = (
            await connection.execute(
                text(
                    """
                    SELECT u.id, p.version
                    FROM accounts.users u
                    JOIN accounts.sessions s ON s.user_id=u.id
                    JOIN accounts.profiles p ON p.user_id=u.id
                    WHERE s.token_hash=:token_hash
                      AND s.csrf_token_hash=:csrf_hash
                      AND s.revoked_at IS NULL AND s.expires_at>now()
                      AND u.status='active'
                    FOR UPDATE OF u, s, p
                    """
                ),
                {
                    "token_hash": credential_hash(auth_secret, token),
                    "csrf_hash": credential_hash(auth_secret, csrf_token),
                },
            )
        ).mappings().one_or_none()
        if row is None:
            return None
        if row["version"] != expected_profile_version:
            raise ValueError("stale_profile")
        city_exists = await connection.scalar(
            text("SELECT 1 FROM discovery.cities WHERE id=:id AND is_active"),
            {"id": selected_city_id},
        )
        if city_exists is None:
            raise ValueError("invalid_city")
        accepted_at = datetime.now(UTC)
        await connection.execute(
            text(
                """
                INSERT INTO accounts.age_acceptances
                    (id, user_id, rule_version, accepted_at)
                VALUES (:id, :user_id, :rule_version, :accepted_at)
                ON CONFLICT (user_id, rule_version) DO NOTHING
                """
            ),
            {
                "id": uuid4(),
                "user_id": row["id"],
                "rule_version": AGE_RULE_VERSION,
                "accepted_at": accepted_at,
            },
        )
        await connection.execute(
            text(
                """
                UPDATE accounts.users
                SET accepted_age_rule_version=:rule_version,
                    accepted_age_rule_at=COALESCE(accepted_age_rule_at, :accepted_at),
                    updated_at=now()
                WHERE id=:user_id
                """
            ),
            {
                "user_id": row["id"],
                "rule_version": AGE_RULE_VERSION,
                "accepted_at": accepted_at,
            },
        )
        updated = await connection.scalar(
            text(
                """
                UPDATE accounts.profiles
                SET selected_city_id=:city, version=version+1, updated_at=now()
                WHERE user_id=:user_id AND version=:version
                RETURNING user_id
                """
            ),
            {
                "city": selected_city_id,
                "user_id": row["id"],
                "version": expected_profile_version,
            },
        )
        if updated is None:
            raise ValueError("stale_profile")
    return await load_session_profile(engine, token=token, auth_secret=auth_secret)


async def revoke_session(
    engine: AsyncEngine,
    *,
    token: str,
    csrf_token: str,
    auth_secret: bytes,
) -> bool:
    async with engine.begin() as connection:
        revoked_id = (
            await connection.execute(
            text(
                """
                UPDATE accounts.sessions
                SET revoked_at = now()
                WHERE token_hash = :token_hash
                  AND csrf_token_hash = :csrf_hash
                  AND revoked_at IS NULL
                RETURNING id
                """
            ),
            {
                "token_hash": credential_hash(auth_secret, token),
                "csrf_hash": credential_hash(auth_secret, csrf_token),
            },
            )
        ).scalar_one_or_none()
    return revoked_id is not None


async def _reserve_public_id(connection: AsyncConnection) -> str:
    for _ in range(10):
        candidate = f"{secrets.randbelow(100_000_000):08d}"
        result = await connection.execute(
            text(
                "SELECT 1 FROM accounts.profiles WHERE public_id = :public_id"
            ),
            {"public_id": candidate},
        )
        if result.scalar_one_or_none() is None:
            return candidate
    raise RuntimeError("could not allocate public profile ID")


def _profile_from_row(row: Mapping[str, Any]) -> AccountProfile:
    return AccountProfile(
        user_id=row["id"],
        public_id=row["public_id"],
        display_name=row["display_name"],
        bio=row["bio"],
        selected_city_id=row["selected_city_id"],
        age_confirmed=row["accepted_age_rule_at"] is not None,
    )
