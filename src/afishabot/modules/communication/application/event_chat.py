"""Event chat: message listing, sending and organizer-controlled availability."""

from datetime import timedelta
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class ChatError(Exception):
    pass


class ChatForbidden(ChatError):
    """Viewer is neither the organizer nor an active participant."""


class ChatClosed(ChatError):
    """The organizer has closed the chat."""


class EventNotActive(ChatError):
    """The event is not available for chat."""


class ChatIdempotencyReused(ChatError):
    """The same idempotency key was used with different content."""


def _fingerprint(*parts: object) -> str:
    return sha256("\x1f".join(str(part) for part in parts).encode()).hexdigest()


async def _existing_request(
    connection: Any, user_id: UUID, key: UUID, fingerprint: str
) -> UUID | None:
    await connection.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"event-chat:{user_id}:{key}"},
    )
    row = (
        (
            await connection.execute(
                text("""
        SELECT request_fingerprint, message_id
        FROM communication.chat_message_requests
        WHERE user_id=:user AND idempotency_key=:key FOR UPDATE
    """),
                {"user": user_id, "key": key},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    if row["request_fingerprint"] != fingerprint:
        raise ChatIdempotencyReused("idempotency_key_reused")
    return row["message_id"]


async def _remember_request(
    connection: Any, user_id: UUID, key: UUID, fingerprint: str, resource_id: UUID
) -> None:
    await connection.execute(
        text("""
        INSERT INTO communication.chat_message_requests
               (user_id, idempotency_key, request_fingerprint, message_id)
        VALUES (:user,:key,:fingerprint,:message)
    """),
        {
            "user": user_id,
            "key": key,
            "fingerprint": fingerprint,
            "message": resource_id,
        },
    )


async def _event_for_chat(connection: Any, event_id: UUID) -> dict[str, Any] | None:
    row = (
        (
            await connection.execute(
                text("""
        SELECT e.id, e.creator_user_id, e.lifecycle_status, e.chat_enabled,
               e.event_scope, r.ends_at
        FROM events.events e
        JOIN events.event_revisions r ON r.id = e.approved_revision_id
        WHERE e.id = :id
        FOR UPDATE OF e
    """),
                {"id": event_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else None


async def _active_episode(
    connection: Any, event_id: UUID, user_id: UUID
) -> UUID | None:
    episode = await connection.scalar(
        text("""
        SELECT id FROM events.participation_episodes
        WHERE event_id=:event AND user_id=:user
          AND status='active' AND closed_at IS NULL
        LIMIT 1
    """),
        {"event": event_id, "user": user_id},
    )
    return episode


async def _message_payload(
    connection: Any,
    message_id: UUID,
    creator_user_id: UUID,
    viewer_user_id: UUID,
) -> dict[str, Any]:
    row = (
        (
            await connection.execute(
                text("""
        SELECT m.body, m.created_at, pr.public_id, pr.display_name,
               pr.avatar_asset_id,
               (m.author_user_id = :creator) AS is_organizer,
               (m.author_user_id = :viewer) AS is_viewer
        FROM communication.messages m
        JOIN accounts.profiles pr ON pr.user_id = m.author_user_id
        WHERE m.id = :id
    """),
                {
                    "id": message_id,
                    "creator": creator_user_id,
                    "viewer": viewer_user_id,
                },
            )
        )
        .mappings()
        .one()
    )
    return {
        "id": message_id,
        "body": row["body"],
        "created_at": row["created_at"].isoformat(),
        "author_display_name": row["display_name"],
        "author_public_id": row.get("public_id", ""),
        "author_avatar_thumbnail_url": (
            f"/api/profiles/{row['public_id']}/avatar?size=64"
            if row.get("avatar_asset_id") and row.get("public_id") else None
        ),
        "author_is_organizer": row["is_organizer"],
        "author_is_viewer": row["is_viewer"],
    }


async def ensure_chat_access(
    engine: AsyncEngine, *, event_id: UUID, user_id: UUID
) -> dict[str, Any]:
    """Resolve event access; bookkept so the HTTP layer can query chat_enabled."""
    async with engine.connect() as connection:
        event = await _event_for_chat(connection, event_id)
        if event is None:
            raise EventNotActive("event_not_found")
        if event["event_scope"] == "community":
            raise ChatForbidden("chat_not_allowed")
        episode = await _active_episode(connection, event_id, user_id)
        if episode is None and event["creator_user_id"] != user_id:
            raise ChatForbidden("chat_forbidden")
        return event


async def list_messages(
    engine: AsyncEngine,
    *,
    event_id: UUID,
    viewer_id: UUID,
    after: UUID | None = None,
    limit: int = 200,
) -> tuple[list[dict[str, Any]], bool]:
    async with engine.connect() as connection:
        event = await _event_for_chat(connection, event_id)
        if event is None:
            raise EventNotActive("event_not_found")
        if event["event_scope"] == "community":
            raise ChatForbidden("chat_not_allowed")
        episode = await _active_episode(connection, event_id, viewer_id)
        if episode is None and event["creator_user_id"] != viewer_id:
            raise ChatForbidden("chat_forbidden")
        params: dict[str, Any] = {
            "event": event_id,
            "limit": limit + 1,
            "creator": event["creator_user_id"],
            "viewer": viewer_id,
        }
        after_clause = ""
        if after is not None:
            after_clause = "AND m.id > CAST(:after AS uuid)"
            params["after"] = after
        rows = (
            (
                await connection.execute(
                    text(f"""
            SELECT m.id, m.body, m.created_at, pr.public_id, pr.display_name,
               pr.avatar_asset_id,
               (m.author_user_id = :creator) AS is_organizer,
               (m.author_user_id = :viewer) AS is_viewer
            FROM communication.messages m
            JOIN accounts.profiles pr ON pr.user_id = m.author_user_id
            WHERE m.event_id = CAST(:event AS uuid) AND m.delete_after > now()
            {after_clause}
            ORDER BY m.created_at, m.id
            LIMIT :limit
        """),
                    params,
                )
            )
            .mappings()
            .all()
        )
        items = [
            {
                "id": row["id"],
                "body": row["body"],
                "created_at": row["created_at"].isoformat(),
                "author_display_name": row["display_name"],
                "author_public_id": row["public_id"],
                "author_avatar_thumbnail_url": (
                    f"/api/profiles/{row['public_id']}/avatar?size=64"
                    if row["avatar_asset_id"] else None
                ),
                "author_is_organizer": row["is_organizer"],
                "author_is_viewer": row["is_viewer"],
            }
            for row in rows[:limit]
        ]
        return items, len(rows) > limit


async def send_message(
    engine: AsyncEngine,
    *,
    event_id: UUID,
    user_id: UUID,
    body: str,
    idempotency_key: UUID,
) -> dict[str, Any]:
    body = body.strip()
    fingerprint = _fingerprint("message", event_id, body)
    async with engine.begin() as connection:
        previous = await _existing_request(
            connection, user_id, idempotency_key, fingerprint
        )
        if previous is not None:
            event = await _event_for_chat(connection, event_id)
            return await _message_payload(
                connection,
                previous,
                event["creator_user_id"] if event else user_id,
                user_id,
            )
        event = await _event_for_chat(connection, event_id)
        if event is None:
            raise EventNotActive("event_not_found")
        if event["event_scope"] == "community":
            raise ChatForbidden("chat_not_allowed")
        if event["lifecycle_status"] != "published":
            raise EventNotActive("event_not_active")
        if not event["chat_enabled"]:
            raise ChatClosed("chat_closed")
        episode = await _active_episode(connection, event_id, user_id)
        if episode is None and event["creator_user_id"] != user_id:
            raise ChatForbidden("chat_forbidden")
        message_id = uuid4()
        await connection.execute(
            text("""
            INSERT INTO communication.messages
              (id, event_id, author_user_id, participation_episode_id, body,
               created_at, delete_after)
            VALUES (:id, :event, :author, :episode, :body, now(), :delete_after)
        """),
            {
                "id": message_id,
                "event": event_id,
                "author": user_id,
                "episode": episode or uuid4(),
                "body": body,
                "delete_after": event["ends_at"] + timedelta(hours=24),
            },
        )
        await _remember_request(
            connection, user_id, idempotency_key, fingerprint, message_id
        )
        return await _message_payload(
            connection,
            message_id,
            event["creator_user_id"],
            user_id,
        )


async def set_chat_enabled(
    engine: AsyncEngine, *, event_id: UUID, user_id: UUID, enabled: bool
) -> bool:
    async with engine.begin() as connection:
        event = await _event_for_chat(connection, event_id)
        if event is None:
            raise EventNotActive("event_not_found")
        if event["event_scope"] == "community":
            raise ChatForbidden("chat_not_allowed")
        if event["creator_user_id"] != user_id:
            raise ChatForbidden("chat_forbidden")
        await connection.execute(
            text("UPDATE events.events SET chat_enabled=:enabled WHERE id=:id"),
            {"enabled": enabled, "id": event_id},
        )
        return enabled
