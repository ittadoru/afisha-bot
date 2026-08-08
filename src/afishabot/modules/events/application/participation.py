from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

MembershipState = Literal["none", "participating", "waitlisted", "excluded"]
ExclusionReason = Literal[
    "rules_violation", "disruptive_behavior", "participant_request", "other"
]

EXCLUSION_REASONS = {
    "rules_violation": "Нарушение правил",
    "disruptive_behavior": "Мешает проведению события",
    "participant_request": "По просьбе участника",
    "other": "Другая причина",
}


class ParticipationError(Exception):
    pass


class ParticipationNotFound(ParticipationError):
    pass


async def set_interest(
    engine: AsyncEngine, *, event_id: UUID, user_id: UUID, active: bool
) -> dict[str, Any]:
    async with engine.begin() as connection:
        event = (
            await connection.execute(
                text(
                    """
                    SELECT e.id
                    FROM events.events e
                    JOIN events.event_revisions r ON r.id=e.approved_revision_id
                    WHERE e.id=:event AND e.lifecycle_status='published'
                      AND r.ends_at>now()
                    """
                ),
                {"event": event_id},
            )
        ).scalar_one_or_none()
        if event is None:
            raise ParticipationNotFound("event_not_active")
        await connection.execute(
            text(
                """
                INSERT INTO events.event_interests
                    (event_id,user_id,active,created_at,updated_at)
                VALUES (:event,:user,:active,now(),now())
                ON CONFLICT (event_id,user_id) DO UPDATE
                SET active=EXCLUDED.active,updated_at=now()
                """
            ),
            {"event": event_id, "user": user_id, "active": active},
        )
        count = await connection.scalar(
            text(
                "SELECT count(*) FROM events.event_interests "
                "WHERE event_id=:event AND active"
            ),
            {"event": event_id},
        )
    return {"interested": active, "interest_count": int(count or 0)}


async def join_event(
    engine: AsyncEngine, *, event_id: UUID, user_id: UUID
) -> dict[str, Any]:
    async with engine.begin() as connection:
        event = await _locked_active_event(connection, event_id)
        if event["kind"] != "regular":
            raise ParticipationError("special_event_has_no_participation")
        if event["creator_user_id"] == user_id:
            raise ParticipationError("organizer_cannot_join")
        if await _was_excluded(connection, event_id, user_id):
            raise ParticipationError("participant_excluded")

        active = await connection.scalar(
            text(
                "SELECT id FROM events.participation_episodes "
                "WHERE event_id=:event AND user_id=:user AND status='active'"
            ),
            {"event": event_id, "user": user_id},
        )
        if active is not None:
            return {"state": "participating", "queue_position": None}

        waiting = await _waiting_entry(connection, event_id, user_id)
        if waiting is not None:
            return {
                "state": "waitlisted",
                "queue_position": await _queue_position(
                    connection, event_id, int(waiting["queue_order"])
                ),
            }

        participant_count = int(
            await connection.scalar(
                text(
                    "SELECT count(*) FROM events.participation_episodes "
                    "WHERE event_id=:event AND status='active'"
                ),
                {"event": event_id},
            )
            or 0
        )
        capacity = event["capacity"]
        if capacity is None or participant_count < capacity:
            await connection.execute(
                text(
                    """
                    INSERT INTO events.participation_episodes
                        (id,event_id,user_id,status,joined_at)
                    VALUES (:id,:event,:user,'active',now())
                    """
                ),
                {"id": uuid4(), "event": event_id, "user": user_id},
            )
            return {"state": "participating", "queue_position": None}

        entry = (
            (
                await connection.execute(
                    text(
                        """
                    INSERT INTO events.waitlist_entries (id,event_id,user_id)
                    VALUES (:id,:event,:user)
                    RETURNING queue_order
                    """
                    ),
                    {"id": uuid4(), "event": event_id, "user": user_id},
                )
            )
            .mappings()
            .one()
        )
        return {
            "state": "waitlisted",
            "queue_position": await _queue_position(
                connection, event_id, int(entry["queue_order"])
            ),
        }


async def leave_event(
    engine: AsyncEngine, *, event_id: UUID, user_id: UUID
) -> dict[str, Any]:
    async with engine.begin() as connection:
        await _locked_active_event(connection, event_id)
        waiting = await _waiting_entry(connection, event_id, user_id)
        if waiting is not None:
            await connection.execute(
                text(
                    """
                    UPDATE events.waitlist_entries
                    SET status='left',closed_at=now()
                    WHERE id=:id AND status='waiting'
                    """
                ),
                {"id": waiting["id"]},
            )
            return {"state": "none", "promoted_user_id": None}

        episode = await connection.scalar(
            text(
                "SELECT id FROM events.participation_episodes "
                "WHERE event_id=:event AND user_id=:user AND status='active' FOR UPDATE"
            ),
            {"event": event_id, "user": user_id},
        )
        if episode is None:
            raise ParticipationError("not_participating")
        await connection.execute(
            text(
                """
                UPDATE events.participation_episodes
                SET status='left',closed_at=now(),close_reason='voluntary_leave'
                WHERE id=:episode
                """
            ),
            {"episode": episode},
        )
        promoted = await _promote_next(connection, event_id)
        return {"state": "none", "promoted_user_id": promoted}


async def exclude_participant(
    engine: AsyncEngine,
    *,
    event_id: UUID,
    organizer_id: UUID,
    participation_id: UUID,
    reason: ExclusionReason,
    note: str | None,
) -> None:
    if reason not in EXCLUSION_REASONS:
        raise ParticipationError("invalid_exclusion_reason")
    normalized_note = " ".join((note or "").split()) or None
    if reason == "other" and normalized_note is None:
        raise ParticipationError("exclusion_note_required")
    if normalized_note is not None and len(normalized_note) > 300:
        raise ParticipationError("exclusion_note_too_long")

    async with engine.begin() as connection:
        event = await _locked_active_event(connection, event_id)
        if event["kind"] != "regular" or event["creator_user_id"] != organizer_id:
            raise ParticipationNotFound("event_not_owned")
        participant = (
            (
                await connection.execute(
                    text(
                        """
                    SELECT id,user_id FROM events.participation_episodes
                    WHERE id=:episode AND event_id=:event AND status='active'
                    FOR UPDATE
                    """
                    ),
                    {"episode": participation_id, "event": event_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if participant is None:
            raise ParticipationNotFound("participant_not_found")
        await connection.execute(
            text(
                """
                UPDATE events.participation_episodes
                SET status='excluded',closed_at=now(),close_reason=:reason,
                    close_note=:note,excluded_by_user_id=:organizer
                WHERE id=:episode
                """
            ),
            {
                "episode": participation_id,
                "reason": reason,
                "note": normalized_note,
                "organizer": organizer_id,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO communication.notifications
                    (id,recipient_user_id,kind,importance,title,body,
                     subject_type,subject_id,deep_link)
                VALUES (:id,:user,'event_participation_excluded','critical',
                        'Участие завершено',:body,'event',:event,
                        '/app/event/' || CAST(:event AS text))
                """
            ),
            {
                "id": uuid4(),
                "user": participant["user_id"],
                "event": str(event_id),
                "body": EXCLUSION_REASONS[reason],
            },
        )
        await _promote_next(connection, event_id)


async def organizer_roster(
    engine: AsyncEngine, *, event_id: UUID, organizer_id: UUID
) -> dict[str, Any]:
    async with engine.connect() as connection:
        owner = await connection.scalar(
            text(
                """
                SELECT 1 FROM events.events e
                JOIN events.event_revisions r ON r.id=e.approved_revision_id
                WHERE e.id=:event AND e.kind='regular'
                  AND e.creator_user_id=:organizer AND r.ends_at>now()
                """
            ),
            {"event": event_id, "organizer": organizer_id},
        )
        if owner is None:
            raise ParticipationNotFound("event_not_owned")
        participants = (
            (
                await connection.execute(
                    text(
                        """
                    SELECT p.id AS participation_id,profile.public_id,
                           profile.display_name,p.joined_at
                    FROM events.participation_episodes p
                    JOIN accounts.profiles profile ON profile.user_id=p.user_id
                    WHERE p.event_id=:event AND p.status='active'
                    ORDER BY p.joined_at,p.id
                    """
                    ),
                    {"event": event_id},
                )
            )
            .mappings()
            .all()
        )
        waitlist = (
            (
                await connection.execute(
                    text(
                        """
                    SELECT profile.public_id,profile.display_name,w.queued_at,
                           row_number() OVER (ORDER BY w.queue_order) AS position
                    FROM events.waitlist_entries w
                    JOIN accounts.profiles profile ON profile.user_id=w.user_id
                    WHERE w.event_id=:event AND w.status='waiting'
                    ORDER BY w.queue_order
                    """
                    ),
                    {"event": event_id},
                )
            )
            .mappings()
            .all()
        )
    return {
        "participants": [dict(row) for row in participants],
        "waitlist": [dict(row) for row in waitlist],
    }


async def _locked_active_event(
    connection: AsyncConnection, event_id: UUID
) -> dict[str, Any]:
    event = (
        (
            await connection.execute(
                text(
                    """
                SELECT e.id,e.kind,e.creator_user_id,e.capacity,r.title
                FROM events.events e
                JOIN events.event_revisions r ON r.id=e.approved_revision_id
                WHERE e.id=:event AND e.lifecycle_status='published'
                  AND r.ends_at>now()
                FOR UPDATE OF e
                """
                ),
                {"event": event_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if event is None:
        raise ParticipationNotFound("event_not_active")
    return dict(event)


async def _was_excluded(
    connection: AsyncConnection, event_id: UUID, user_id: UUID
) -> bool:
    return bool(
        await connection.scalar(
            text(
                """
                SELECT 1 FROM events.participation_episodes
                WHERE event_id=:event AND user_id=:user AND status='excluded'
                LIMIT 1
                """
            ),
            {"event": event_id, "user": user_id},
        )
    )


async def _waiting_entry(
    connection: AsyncConnection, event_id: UUID, user_id: UUID
) -> dict[str, Any] | None:
    row = (
        (
            await connection.execute(
                text(
                    """
                SELECT id,queue_order FROM events.waitlist_entries
                WHERE event_id=:event AND user_id=:user AND status='waiting'
                """
                ),
                {"event": event_id, "user": user_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else None


async def _queue_position(
    connection: AsyncConnection, event_id: UUID, queue_order: int
) -> int:
    return int(
        await connection.scalar(
            text(
                """
                SELECT count(*) FROM events.waitlist_entries
                WHERE event_id=:event AND status='waiting'
                  AND queue_order<=:queue_order
                """
            ),
            {"event": event_id, "queue_order": queue_order},
        )
        or 0
    )


async def _promote_next(connection: AsyncConnection, event_id: UUID) -> UUID | None:
    entry = (
        (
            await connection.execute(
                text(
                    """
                SELECT id,user_id FROM events.waitlist_entries
                WHERE event_id=:event AND status='waiting'
                ORDER BY queue_order
                LIMIT 1 FOR UPDATE
                """
                ),
                {"event": event_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if entry is None:
        return None
    await connection.execute(
        text(
            """
            UPDATE events.waitlist_entries
            SET status='promoted',closed_at=now()
            WHERE id=:id AND status='waiting'
            """
        ),
        {"id": entry["id"]},
    )
    await connection.execute(
        text(
            """
            INSERT INTO events.participation_episodes
                (id,event_id,user_id,status,joined_at)
            VALUES (:id,:event,:user,'active',now())
            """
        ),
        {"id": uuid4(), "event": event_id, "user": entry["user_id"]},
    )
    await connection.execute(
        text(
            """
            INSERT INTO communication.notifications
                (id,recipient_user_id,kind,importance,title,body,
                 subject_type,subject_id,deep_link)
            SELECT :id,:user,'waitlist_promoted','critical','Вы стали участником',
                   'Для вас освободилось место на событии «'
                     || r.title || '».',
                   'event',e.id,'/app/event/' || CAST(e.id AS text)
            FROM events.events e
            JOIN events.event_revisions r ON r.id=e.approved_revision_id
            WHERE e.id=:event
            """
        ),
        {"id": uuid4(), "user": entry["user_id"], "event": event_id},
    )
    return entry["user_id"]
