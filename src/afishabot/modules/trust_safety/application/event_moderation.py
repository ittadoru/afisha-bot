from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

REJECTION_REASONS = {
    "unclear_description": "Непонятное или неполное описание",
    "prohibited_content": "Запрещённый контент",
    "paid_or_advertising": "Платное или рекламное событие",
    "inappropriate_photo": "Неподходящая фотография",
    "invalid_place_or_time": "Неверное место или время",
    "duplicate_or_spam": "Дубликат или спам",
}


class ModerationConflict(Exception):
    pass


class ModerationNotFound(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    review_id: UUID
    revision_id: UUID
    staff_id: UUID
    action: Literal["approve", "reject"]
    reason: str | None = None


async def review_queue(
    engine: AsyncEngine, *, offset: int, limit: int
) -> list[dict[str, Any]]:
    async with engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    text(
                        """
                    SELECT q.id, q.event_id, q.event_revision_id, q.submitted_at,
                           r.title, r.starts_at, c.name AS city,
                           p.public_id, p.display_name
                    FROM trust_safety.event_reviews q
                    JOIN events.event_revisions r ON r.id=q.event_revision_id
                    JOIN events.events e ON e.id=q.event_id
                    JOIN discovery.cities c ON c.id=e.city_id
                    JOIN accounts.profiles p ON p.user_id=e.creator_user_id
                    WHERE q.status='pending'
                      AND e.lifecycle_status IN ('pending','published')
                      AND e.current_revision_id=q.event_revision_id
                    ORDER BY q.submitted_at, q.id
                    LIMIT :limit OFFSET :offset
                    """
                    ),
                    {"limit": limit, "offset": offset},
                )
            )
            .mappings()
            .all()
        )
    return [dict(row) for row in rows]


async def review_detail(engine: AsyncEngine, review_id: UUID) -> dict[str, Any]:
    async with engine.connect() as connection:
        row = (
            (
                await connection.execute(
                    text(
                        """
                    SELECT q.id, q.event_id, q.event_revision_id, q.submitted_at,
                           r.title, r.description, r.starts_at, r.ends_at,
                           r.normalized_address, r.street_name, r.landmark,
                           r.address_visibility,
                           ST_Y(r.location::geometry) AS latitude,
                           ST_X(r.location::geometry) AS longitude,
                           e.capacity, c.name AS city, cat.name AS category,
                           p.public_id, p.display_name,
                           o.status AS organizer_status,
                           o.successful_events, ep.media_asset_id
                    FROM trust_safety.event_reviews q
                    JOIN events.event_revisions r ON r.id=q.event_revision_id
                    JOIN events.events e ON e.id=q.event_id
                    JOIN discovery.cities c ON c.id=e.city_id
                    JOIN discovery.categories cat ON cat.id=e.category_id
                    JOIN accounts.profiles p ON p.user_id=e.creator_user_id
                    JOIN reputation.organizer_profiles o ON o.user_id=e.creator_user_id
                    JOIN events.event_photos ep ON ep.revision_id=r.id AND ep.position=1
                    WHERE q.id=:review AND q.status='pending'
                      AND e.current_revision_id=q.event_revision_id
                    """
                    ),
                    {"review": review_id},
                )
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise ModerationNotFound
    return dict(row)


async def decide_review(engine: AsyncEngine, decision: ReviewDecision) -> None:
    if decision.action == "reject" and decision.reason not in REJECTION_REASONS:
        raise ModerationConflict("invalid_rejection_reason")
    async with engine.begin() as connection:
        row = (
            (
                await connection.execute(
                    text(
                        """
                    SELECT q.event_id, q.event_revision_id, e.creator_user_id,
                           e.lifecycle_status, e.approved_revision_id,
                           e.schedule_changes_used, r.title, r.description,
                           r.starts_at, r.ends_at, ep.media_asset_id,
                           old.title AS old_title,
                           old.description AS old_description,
                           old.starts_at AS old_starts_at,
                           old.ends_at AS old_ends_at,
                           old_photo.media_asset_id AS old_media_asset_id
                    FROM trust_safety.event_reviews q
                    JOIN events.events e ON e.id=q.event_id
                    JOIN events.event_revisions r ON r.id=q.event_revision_id
                    JOIN events.event_photos ep
                      ON ep.revision_id=r.id AND ep.position=1
                    LEFT JOIN events.event_revisions old
                      ON old.id=e.approved_revision_id
                    LEFT JOIN events.event_photos old_photo
                      ON old_photo.revision_id=old.id AND old_photo.position=1
                    WHERE q.id=:review AND q.status='pending'
                      AND e.current_revision_id=q.event_revision_id
                    FOR UPDATE OF q, e, r
                    """
                    ),
                    {"review": decision.review_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ModerationConflict("review_already_decided")
        if row["event_revision_id"] != decision.revision_id:
            raise ModerationConflict("stale_review")
        if (
            decision.action == "approve"
            and row["starts_at"] <= datetime.now().astimezone()
        ):
            raise ModerationConflict("event_already_started")

        approved = decision.action == "approve"
        review_status = "approved" if approved else "rejected"
        is_published_change = row["approved_revision_id"] is not None
        lifecycle = "published" if approved or is_published_change else "rejected"
        event_moderation = (
            "approved" if is_published_change and not approved else review_status
        )
        schedule_changed = is_published_change and (
            row["starts_at"] != row["old_starts_at"]
            or row["ends_at"] != row["old_ends_at"]
        )
        if approved and schedule_changed and row["schedule_changes_used"] >= 1:
            raise ModerationConflict("schedule_change_already_used")
        await connection.execute(
            text(
                """
                UPDATE trust_safety.event_reviews
                SET status=:status, decided_by_staff_id=:staff,
                    normalized_reason_code=:reason, decided_at=now()
                WHERE id=:review
                """
            ),
            {
                "status": review_status,
                "staff": decision.staff_id,
                "reason": decision.reason,
                "review": decision.review_id,
            },
        )
        await connection.execute(
            text(
                "UPDATE events.event_revisions SET moderation_status=:status, "
                "decided_at=now() WHERE id=:revision"
            ),
            {"status": review_status, "revision": decision.revision_id},
        )
        await connection.execute(
            text(
                """
                UPDATE events.events
                SET lifecycle_status=:lifecycle, moderation_status=:event_status,
                    approved_revision_id=CASE
                      WHEN :approved THEN CAST(:revision AS uuid) ELSE approved_revision_id END,
                    schedule_changes_used=schedule_changes_used+
                      CASE WHEN :schedule_changed AND :approved THEN 1 ELSE 0 END,
                    version=version+1, updated_at=now()
                WHERE id=:event AND current_revision_id=:revision
                """
            ),
            {
                "lifecycle": lifecycle,
                "event_status": event_moderation,
                "approved": approved,
                "revision": decision.revision_id,
                "event": row["event_id"],
                "schedule_changed": schedule_changed,
            },
        )
        conversion = (
            await connection.execute(
                text(
                    """
                    SELECT id, status FROM discovery.looking_posts
                    WHERE pending_event_id=:event FOR UPDATE
                    """
                ),
                {"event": row["event_id"]},
            )
        ).mappings().one_or_none()
        if conversion is not None:
            if approved:
                await connection.execute(
                    text(
                        """
                        UPDATE discovery.looking_posts
                        SET status='converted', converted_event_id=:event,
                            pending_event_id=NULL, closed_at=now(),
                            delete_after=now()+interval '24 hours', version=version+1
                        WHERE id=:post
                        """
                    ),
                    {"event": row["event_id"], "post": conversion["id"]},
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO events.event_interests (event_id, user_id, active, created_at, updated_at)
                        SELECT :event, user_id, true, now(), now()
                        FROM discovery.looking_post_likes
                        WHERE looking_post_id=:post AND active
                        ON CONFLICT (event_id, user_id) DO UPDATE SET active=true, updated_at=now()
                        """
                    ),
                    {"event": row["event_id"], "post": conversion["id"]},
                )
            else:
                await connection.execute(
                    text("UPDATE discovery.looking_posts SET pending_event_id=NULL, version=version+1 WHERE id=:post"),
                    {"post": conversion["id"]},
                )
        reason_text = REJECTION_REASONS.get(decision.reason or "", "")
        await connection.execute(
            text(
                """
                INSERT INTO communication.notifications
                    (id, recipient_user_id, kind, title, body,
                     subject_type, subject_id, deep_link)
                VALUES (:id, :user, :kind, :title, :body,
                        'event', :event, :link)
                """
            ),
            {
                "id": uuid4(),
                "user": row["creator_user_id"],
                "kind": "event_changed_approved"
                if approved and is_published_change
                else "event_approved"
                if approved
                else "event_rejected",
                "title": "Изменения одобрены"
                if approved and is_published_change
                else "Событие опубликовано"
                if approved
                else "Событие нужно исправить",
                "body": row["title"] if approved else reason_text,
                "event": row["event_id"],
                "link": f"/app/event/{row['event_id']}"
                if approved
                else f"/app/event/{row['event_id']}/edit",
            },
        )
        if approved and is_published_change:
            changes: list[str] = []
            if row["title"] != row["old_title"]:
                changes.append(f"Название: {row['old_title']} → {row['title']}")
            if row["description"] != row["old_description"]:
                changes.append("Описание обновлено")
            if schedule_changed:
                changes.append(
                    "Время: "
                    f"{row['old_starts_at'].strftime('%d.%m %H:%M')} → "
                    f"{row['starts_at'].strftime('%d.%m %H:%M')}"
                )
            if row["media_asset_id"] != row["old_media_asset_id"]:
                changes.append("Фотография обновлена")
            await connection.execute(
                text(
                    """
                    INSERT INTO communication.notifications
                        (id,recipient_user_id,kind,importance,title,body,
                         subject_type,subject_id,deep_link)
                    SELECT gen_random_uuid(), p.user_id, 'event_changed',
                           CASE WHEN :schedule_changed THEN 'critical'
                                ELSE 'normal' END,
                           'Событие изменилось', :body, 'event', :event,
                           '/app/event/' || CAST(:event AS text)
                    FROM events.participation_episodes p
                    WHERE p.event_id=:event AND p.status='active'
                    """
                ),
                {
                    "event": row["event_id"],
                    "schedule_changed": schedule_changed,
                    "body": " · ".join(changes),
                },
            )
        await connection.execute(
            text(
                """
                INSERT INTO trust_safety.staff_audit_log
                    (id, actor_staff_id, action, result, details)
                VALUES (:id, :staff, :action, 'success',
                        jsonb_build_object('event_id', CAST(:event AS text),
                                           'review_id', CAST(:review AS text),
                                           'reason', CAST(:reason AS text)))
                """
            ),
            {
                "id": uuid4(),
                "staff": decision.staff_id,
                "action": f"event.{decision.action}",
                "event": row["event_id"],
                "review": decision.review_id,
                "reason": decision.reason,
            },
        )
