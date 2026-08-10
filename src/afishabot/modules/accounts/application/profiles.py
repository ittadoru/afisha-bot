import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from afishabot.modules.accounts.application.auth import credential_hash

NAME_COOLDOWN = timedelta(days=7)


class ProfileError(Exception):
    pass


class ProfileNotFound(ProfileError):
    pass


class ProfileConflict(ProfileError):
    pass


@dataclass(frozen=True, slots=True)
class ProfileView:
    user_id: UUID
    public_id: str
    display_name: str
    bio: str | None
    selected_city_id: UUID | None
    city_name: str | None
    avatar_asset_id: UUID | None
    background_asset_id: UUID | None
    version: int
    next_name_change_at: datetime | None
    organizer_status: str
    successful_events: int
    upcoming_count: int
    completed_count: int


def normalize_display_name(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.strip())
    if not 3 <= len(normalized) <= 32:
        raise ProfileError("invalid_display_name")
    if not all(character.isalnum() or character in " -_" for character in normalized):
        raise ProfileError("invalid_display_name")
    if "http" in normalized.casefold() or "www" in normalized.casefold():
        raise ProfileError("invalid_display_name")
    return normalized


def normalize_bio(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if len(normalized) > 150 or any(
        ord(character) < 32 and character not in "\n\t" for character in normalized
    ):
        raise ProfileError("invalid_bio")
    return normalized or None


async def session_user_id(
    engine: AsyncEngine,
    *,
    token: str,
    auth_secret: bytes,
    csrf_token: str | None = None,
) -> UUID | None:
    csrf_clause = "AND s.csrf_token_hash = :csrf_hash" if csrf_token is not None else ""
    params: dict[str, object] = {"token_hash": credential_hash(auth_secret, token)}
    if csrf_token is not None:
        params["csrf_hash"] = credential_hash(auth_secret, csrf_token)
    async with engine.connect() as connection:
        return await connection.scalar(
            text(
                f"""
                SELECT u.id FROM accounts.sessions s
                JOIN accounts.users u ON u.id = s.user_id
                WHERE s.token_hash = :token_hash {csrf_clause}
                  AND s.revoked_at IS NULL AND s.expires_at > now()
                  AND u.status = 'active'
                """
            ),
            params,
        )


async def load_profile(
    engine: AsyncEngine, *, public_id: str | None = None, user_id: UUID | None = None
) -> ProfileView:
    condition = (
        "p.public_id = :lookup" if public_id is not None else "p.user_id = :lookup"
    )
    lookup: object = public_id if public_id is not None else user_id
    async with engine.connect() as connection:
        row = (
            (
                await connection.execute(
                    text(
                        f"""
                    SELECT p.user_id, p.public_id, p.display_name, p.bio,
                           p.selected_city_id, c.name AS city_name, p.avatar_asset_id,
                           p.background_asset_id,
                           p.version, p.display_name_changed_at,
                           COALESCE(o.status, 'new') AS organizer_status,
                           COALESCE(o.successful_events, 0) AS successful_events,
                           count(e.id) FILTER (WHERE e.lifecycle_status = 'published' AND e.moderation_status = 'approved') AS upcoming_count,
                           count(e.id) FILTER (WHERE e.lifecycle_status = 'finished' AND e.moderation_status = 'approved') AS completed_count
                    FROM accounts.profiles p
                    JOIN accounts.users u ON u.id = p.user_id AND u.status = 'active'
                    LEFT JOIN discovery.cities c ON c.id = p.selected_city_id
                    LEFT JOIN reputation.organizer_profiles o ON o.user_id = p.user_id
                    LEFT JOIN events.events e ON e.creator_user_id = p.user_id
                    WHERE {condition}
                    GROUP BY p.user_id, p.public_id, p.display_name, p.bio,
                             p.selected_city_id, c.name, p.avatar_asset_id,
                             p.background_asset_id, p.version,
                             p.display_name_changed_at, o.status, o.successful_events
                    """
                    ),
                    {"lookup": lookup},
                )
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise ProfileNotFound
    changed_at = row["display_name_changed_at"]
    next_change = None if changed_at is None else changed_at + NAME_COOLDOWN
    return ProfileView(
        user_id=row["user_id"],
        public_id=row["public_id"],
        display_name=row["display_name"],
        bio=row["bio"],
        selected_city_id=row["selected_city_id"],
        city_name=row["city_name"],
        avatar_asset_id=row["avatar_asset_id"],
        background_asset_id=row["background_asset_id"],
        version=row["version"],
        next_name_change_at=next_change,
        organizer_status=row["organizer_status"],
        successful_events=row["successful_events"],
        upcoming_count=row["upcoming_count"],
        completed_count=row["completed_count"],
    )


async def update_profile(
    engine: AsyncEngine,
    *,
    user_id: UUID,
    display_name: str,
    bio: str | None,
    selected_city_id: UUID,
    expected_version: int,
) -> ProfileView:
    name = normalize_display_name(display_name)
    about = normalize_bio(bio)
    async with engine.begin() as connection:
        row = (
            (
                await connection.execute(
                    text(
                        "SELECT display_name, display_name_changed_at FROM accounts.profiles WHERE user_id=:id FOR UPDATE"
                    ),
                    {"id": user_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ProfileNotFound
        city_exists = await connection.scalar(
            text("SELECT 1 FROM discovery.cities WHERE id=:id AND is_active"),
            {"id": selected_city_id},
        )
        if city_exists is None:
            raise ProfileError("invalid_city")
        name_changed = name != row["display_name"]
        if (
            name_changed
            and row["display_name_changed_at"] is not None
            and row["display_name_changed_at"] + NAME_COOLDOWN > datetime.now(UTC)
        ):
            raise ProfileConflict("display_name_cooldown")
        updated = await connection.scalar(
            text(
                """
                UPDATE accounts.profiles SET display_name=CAST(:name AS varchar(32)), bio=:bio,
                    selected_city_id=:city, version=version+1, updated_at=now(),
                    display_name_changed_at=CASE WHEN display_name<>CAST(:name AS varchar(32)) THEN now() ELSE display_name_changed_at END
                WHERE user_id=:id AND version=:version RETURNING user_id
                """
            ),
            {
                "name": name,
                "bio": about,
                "city": selected_city_id,
                "id": user_id,
                "version": expected_version,
            },
        )
        if updated is None:
            raise ProfileConflict("stale_profile")
    return await load_profile(engine, user_id=user_id)


async def update_profile_city(
    engine: AsyncEngine, *, user_id: UUID, selected_city_id: UUID, expected_version: int
) -> ProfileView:
    async with engine.begin() as connection:
        city_exists = await connection.scalar(
            text("SELECT 1 FROM discovery.cities WHERE id=:id AND is_active"),
            {"id": selected_city_id},
        )
        if city_exists is None:
            raise ProfileError("invalid_city")
        updated = await connection.scalar(
            text("""
                UPDATE accounts.profiles
                SET selected_city_id=:city, version=version+1, updated_at=now()
                WHERE user_id=:id AND version=:version RETURNING user_id
            """),
            {"city": selected_city_id, "id": user_id, "version": expected_version},
        )
        if updated is None:
            raise ProfileConflict("stale_profile")
    return await load_profile(engine, user_id=user_id)


async def create_report(
    engine: AsyncEngine,
    *,
    reporter_id: UUID,
    subject: ProfileView,
    reason: str,
    comment: str | None,
) -> None:
    note = comment.strip() if comment is not None else None
    if note is not None and len(note) > 300:
        raise ProfileError("invalid_report")
    if reason not in {"photo", "display_name", "bio", "other"} or (
        reason == "other" and not note
    ):
        raise ProfileError("invalid_report")
    if reporter_id == subject.user_id:
        raise ProfileError("cannot_report_self")
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """INSERT INTO trust_safety.profile_reports
                    (id, reporter_user_id, subject_user_id, reason, comment,
                     avatar_asset_id, background_asset_id)
                    VALUES
                    (:id,:reporter,:subject,:reason,:comment,:avatar,:background)"""
                ),
                {
                    "id": uuid4(),
                    "reporter": reporter_id,
                    "subject": subject.user_id,
                    "reason": reason,
                    "comment": note,
                    "avatar": subject.avatar_asset_id,
                    "background": subject.background_asset_id,
                },
            )
    except IntegrityError as error:
        raise ProfileConflict("report_already_open") from error


async def profile_events(
    engine: AsyncEngine, *, user_id: UUID, state: str, limit: int, offset: int
) -> list[dict[str, Any]]:
    lifecycle = "published" if state == "upcoming" else "finished"
    order = "r.starts_at ASC" if state == "upcoming" else "r.ends_at DESC"
    async with engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    text(f"""SELECT e.id, r.title, r.starts_at, r.ends_at, c.name AS category
                    FROM events.events e JOIN events.event_revisions r ON r.id=e.approved_revision_id
                    JOIN discovery.categories c ON c.id=e.category_id
                    WHERE e.creator_user_id=:user AND e.lifecycle_status=:status
                      AND e.moderation_status='approved'
                    ORDER BY {order} LIMIT :limit OFFSET :offset"""),
                    {
                        "user": user_id,
                        "status": lifecycle,
                        "limit": limit,
                        "offset": offset,
                    },
                )
            )
            .mappings()
            .all()
        )
    return [dict(row) for row in rows]


async def account_events(
    engine: AsyncEngine, *, user_id: UUID, state: str, limit: int, offset: int
) -> list[dict[str, Any]]:
    lifecycle = "published" if state == "upcoming" else "finished"
    order = "starts_at ASC" if state == "upcoming" else "ends_at DESC"
    async with engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    text(f"""SELECT DISTINCT e.id, r.title, r.starts_at, r.ends_at,
                           c.name AS category,
                           CASE WHEN e.creator_user_id=:user THEN 'organizer' ELSE 'participant' END AS role
                    FROM events.events e JOIN events.event_revisions r ON r.id=e.approved_revision_id
                    JOIN discovery.categories c ON c.id=e.category_id
                    LEFT JOIN events.participation_episodes p ON p.event_id=e.id AND p.user_id=:user
                    WHERE e.lifecycle_status=:status AND e.moderation_status='approved'
                      AND (e.creator_user_id=:user OR p.user_id=:user)
                    ORDER BY {order} LIMIT :limit OFFSET :offset"""),
                    {
                        "user": user_id,
                        "status": lifecycle,
                        "limit": limit,
                        "offset": offset,
                    },
                )
            )
            .mappings()
            .all()
        )
    return [dict(row) for row in rows]
