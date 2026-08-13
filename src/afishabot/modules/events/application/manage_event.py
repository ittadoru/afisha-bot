from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

CancelReason = Literal[
    "plans_changed",
    "not_enough_participants",
    "venue_problem",
    "unforeseen_circumstances",
]

CANCEL_REASONS: dict[str, str] = {
    "plans_changed": "Планы изменились",
    "not_enough_participants": "Не набралось участников",
    "venue_problem": "Проблемы с местом",
    "unforeseen_circumstances": "Непредвиденные обстоятельства",
}


class EventManagementError(Exception):
    pass


class EventManagementConflict(EventManagementError):
    pass


class EventManagementNotFound(EventManagementError):
    pass


@dataclass(frozen=True, slots=True)
class ChangeEventCommand:
    event_id: UUID
    user_id: UUID
    idempotency_key: UUID
    request_fingerprint: str
    title: str
    description: str
    starts_at: datetime
    ends_at: datetime
    photo_upload_id: UUID | None


async def management_view(
    engine: AsyncEngine, *, event_id: UUID, user_id: UUID
) -> dict[str, Any]:
    async with engine.connect() as connection:
        row = (
            (
                await connection.execute(
                    text(
                        """
                    SELECT e.id, e.lifecycle_status, e.moderation_status,
                           e.schedule_changes_used,
                           e.current_revision_id, e.approved_revision_id,
                           e.category_id, e.city_id, c.name AS category,
                           city.name AS city, r.title, r.description,
                           r.starts_at, r.ends_at, r.normalized_address,
                           r.organizer_address, r.organizer_street,
                           r.organizer_place, r.street_name, r.address_visibility,
                           ST_Y(r.location::geometry) AS latitude,
                           ST_X(r.location::geometry) AS longitude,
                           ep.media_asset_id,
                           pending.id AS pending_revision_id,
                           pending.moderation_status AS pending_status,
                           q.normalized_reason_code AS rejection_reason
                    FROM events.events e
                    JOIN events.event_revisions r ON r.id=e.approved_revision_id
                    JOIN discovery.categories c ON c.id=e.category_id
                    JOIN discovery.cities city ON city.id=e.city_id
                    JOIN events.event_photos ep
                      ON ep.revision_id=r.id AND ep.position=1
                    LEFT JOIN events.event_revisions pending
                      ON pending.id=e.current_revision_id
                     AND pending.id<>e.approved_revision_id
                    LEFT JOIN trust_safety.event_reviews q
                      ON q.event_revision_id=pending.id
                    WHERE e.id=:event AND e.creator_user_id=:user
                      AND e.kind='regular'
                    """
                    ),
                    {"event": event_id, "user": user_id},
                )
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise EventManagementNotFound
    result = dict(row)
    result["photo_url"] = f"/api/events/{event_id}/manage/photo"
    result["can_edit"] = (
        (
            row["lifecycle_status"] == "published"
            or (
                row["lifecycle_status"] == "hidden"
                and row["moderation_status"] == "held"
            )
        )
        and row["starts_at"] > datetime.now(UTC)
        and row["pending_status"] != "pending"
    )
    result["can_change_schedule"] = row["schedule_changes_used"] == 0
    result["can_cancel"] = row["lifecycle_status"] == "published"
    return result


async def submit_change(engine: AsyncEngine, command: ChangeEventCommand) -> UUID:
    now = datetime.now(UTC)
    if command.ends_at <= command.starts_at:
        raise EventManagementError("end_must_follow_start")
    if command.ends_at > command.starts_at + timedelta(days=7):
        raise EventManagementError("event_too_long")
    if command.starts_at <= now:
        raise EventManagementError("start_must_be_future")

    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"event-change:{command.user_id}:{command.idempotency_key}"},
        )
        previous = (
            (
                await connection.execute(
                    text(
                        """
                    SELECT request_fingerprint, revision_id
                    FROM events.change_requests
                    WHERE user_id=:user AND idempotency_key=:key
                    """
                    ),
                    {"user": command.user_id, "key": command.idempotency_key},
                )
            )
            .mappings()
            .one_or_none()
        )
        if previous is not None:
            if previous["request_fingerprint"] != command.request_fingerprint:
                raise EventManagementConflict("idempotency_key_reused")
            return previous["revision_id"]

        event = (
            (
                await connection.execute(
                    text(
                        """
                    SELECT e.id, e.current_revision_id, e.approved_revision_id,
                           e.schedule_changes_used, r.starts_at AS old_starts,
                           r.ends_at AS old_ends, ep.media_asset_id AS old_photo
                    FROM events.events e
                    JOIN events.event_revisions r ON r.id=e.approved_revision_id
                    JOIN events.event_photos ep
                      ON ep.revision_id=r.id AND ep.position=1
                    WHERE e.id=:event AND e.creator_user_id=:user
                      AND e.kind='regular'
                      AND (e.lifecycle_status='published' OR
                           (e.lifecycle_status='hidden'
                            AND e.moderation_status='held'))
                    FOR UPDATE OF e
                    """
                    ),
                    {"event": command.event_id, "user": command.user_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if event is None:
            raise EventManagementNotFound
        if event["old_starts"] <= now:
            raise EventManagementConflict("event_already_started")
        pending = await connection.scalar(
            text(
                "SELECT 1 FROM events.event_revisions "
                "WHERE event_id=:event AND moderation_status='pending'"
            ),
            {"event": command.event_id},
        )
        if pending is not None:
            raise EventManagementConflict("change_already_pending")
        schedule_changed = (
            command.starts_at != event["old_starts"]
            or command.ends_at != event["old_ends"]
        )
        if schedule_changed and event["schedule_changes_used"] >= 1:
            raise EventManagementConflict("schedule_change_already_used")

        photo_id = command.photo_upload_id or event["old_photo"]
        if command.photo_upload_id is not None:
            photo = await connection.scalar(
                text(
                    """
                    SELECT id FROM media.assets
                    WHERE id=:photo AND owner_user_id=:user
                      AND purpose='event_photo' AND state='ready'
                      AND delete_after>now()
                      AND NOT EXISTS (
                        SELECT 1 FROM events.event_photos ep
                        WHERE ep.media_asset_id=media.assets.id
                      )
                    FOR UPDATE
                    """
                ),
                {"photo": photo_id, "user": command.user_id},
            )
            if photo is None:
                raise EventManagementError("photo_not_available")

        approved = (
            (
                await connection.execute(
                    text(
                        """
                    SELECT r.*, ST_Y(r.location::geometry) AS latitude,
                           ST_X(r.location::geometry) AS longitude
                    FROM events.event_revisions r
                    WHERE r.id=:revision
                    """
                    ),
                    {"revision": event["approved_revision_id"]},
                )
            )
            .mappings()
            .one()
        )
        if (
            " ".join(command.title.split()) == approved["title"]
            and command.description.strip() == approved["description"]
            and not schedule_changed
            and photo_id == event["old_photo"]
        ):
            raise EventManagementError("nothing_changed")
        revision_id = uuid4()
        revision_number = await connection.scalar(
            text(
                "SELECT coalesce(max(revision_number),0)+1 "
                "FROM events.event_revisions WHERE event_id=:event"
            ),
            {"event": command.event_id},
        )
        await connection.execute(
            text(
                """
                INSERT INTO events.event_revisions
                    (id,event_id,revision_number,title,description,rules,landmark,
                     starts_at,ends_at,location,normalized_address,organizer_address,
                     organizer_street,organizer_place,street_name,
                     address_visibility,street_anchor_id,moderation_status)
                VALUES
                    (:id,:event,:number,:title,:description,:rules,:landmark,
                     :starts,:ends,
                     ST_SetSRID(ST_Point(:longitude,:latitude),4326)::geography,
                     :address,:organizer_address,:organizer_street,:organizer_place,
                     :street,:visibility,:street_anchor,'pending')
                """
            ),
            {
                "id": revision_id,
                "event": command.event_id,
                "number": revision_number,
                "title": " ".join(command.title.split()),
                "description": command.description.strip(),
                "rules": approved["rules"],
                "landmark": approved["landmark"],
                "starts": command.starts_at,
                "ends": command.ends_at,
                "longitude": approved["longitude"],
                "latitude": approved["latitude"],
                "address": approved["normalized_address"],
                "organizer_address": approved["organizer_address"],
                "organizer_street": approved["organizer_street"],
                "organizer_place": approved["organizer_place"],
                "street": approved["street_name"],
                "visibility": approved["address_visibility"],
                "street_anchor": approved["street_anchor_id"],
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO events.event_photos
                    (id,event_id,revision_id,media_asset_id,position)
                VALUES (:id,:event,:revision,:photo,1)
                """
            ),
            {
                "id": uuid4(),
                "event": command.event_id,
                "revision": revision_id,
                "photo": photo_id,
            },
        )
        if command.photo_upload_id is not None:
            await connection.execute(
                text("UPDATE media.assets SET delete_after=NULL WHERE id=:photo"),
                {"photo": photo_id},
            )
        review_id = uuid4()
        await connection.execute(
            text(
                """
                INSERT INTO trust_safety.event_reviews
                    (id,event_id,event_revision_id,submitted_by_user_id)
                VALUES (:id,:event,:revision,:user)
                """
            ),
            {
                "id": review_id,
                "event": command.event_id,
                "revision": revision_id,
                "user": command.user_id,
            },
        )
        await connection.execute(
            text(
                "UPDATE events.events SET current_revision_id=:revision,"
                "moderation_status='pending',version=version+1,updated_at=now() "
                "WHERE id=:event"
            ),
            {"revision": revision_id, "event": command.event_id},
        )
        await connection.execute(
            text(
                """
                INSERT INTO events.change_requests
                    (user_id,idempotency_key,request_fingerprint,event_id,revision_id)
                VALUES (:user,:key,:fingerprint,:event,:revision)
                """
            ),
            {
                "user": command.user_id,
                "key": command.idempotency_key,
                "fingerprint": command.request_fingerprint,
                "event": command.event_id,
                "revision": revision_id,
            },
        )
    return revision_id


async def cancel_event(
    engine: AsyncEngine, *, event_id: UUID, user_id: UUID, reason: CancelReason
) -> None:
    if reason not in CANCEL_REASONS:
        raise EventManagementError("invalid_cancel_reason")
    async with engine.begin() as connection:
        row = (
            await connection.execute(
                text(
                    """
                    UPDATE events.events e
                    SET lifecycle_status='cancelled', cancellation_reason_code=:reason,
                        cancelled_at=now(), version=version+1, updated_at=now()
                    WHERE e.id=:event AND e.creator_user_id=:user
                      AND e.kind='regular' AND e.lifecycle_status='published'
                      AND EXISTS (
                        SELECT 1 FROM events.event_revisions r
                        WHERE r.id=e.approved_revision_id AND r.ends_at>now()
                      )
                    RETURNING id
                    """
                ),
                {"event": event_id, "user": user_id, "reason": reason},
            )
        ).scalar_one_or_none()
        if row is None:
            raise EventManagementConflict("event_not_cancellable")
        await connection.execute(
            text(
                """
                UPDATE trust_safety.event_reviews q
                SET status='rejected', normalized_reason_code='event_cancelled',
                    decided_at=now()
                FROM events.event_revisions r
                WHERE q.event_id=:event AND q.status='pending'
                  AND r.id=q.event_revision_id
                """
            ),
            {"event": event_id},
        )
        await connection.execute(
            text(
                """
                UPDATE events.event_revisions
                SET moderation_status='rejected', decided_at=now()
                WHERE event_id=:event AND moderation_status='pending'
                """
            ),
            {"event": event_id},
        )
        await connection.execute(
            text(
                """
                INSERT INTO communication.notifications
                    (id,recipient_user_id,kind,importance,title,body,
                     subject_type,subject_id,deep_link)
                SELECT gen_random_uuid(), p.user_id, 'event_cancelled','critical',
                       'Событие отменено', :body, 'event', :event,
                       '/app/event/' || CAST(:event AS text)
                FROM events.participation_episodes p
                WHERE p.event_id=:event AND p.status='active'
                """
            ),
            {"event": str(event_id), "body": CANCEL_REASONS[reason]},
        )
        await connection.execute(
            text(
                """
                UPDATE events.participation_episodes
                SET status='cancelled', closed_at=now(), close_reason=:reason
                WHERE event_id=:event AND status='active'
                """
            ),
            {"event": event_id, "reason": reason},
        )
        await connection.execute(
            text(
                """
                INSERT INTO communication.notifications
                    (id,recipient_user_id,kind,importance,title,body,
                     subject_type,subject_id,deep_link)
                SELECT gen_random_uuid(), w.user_id, 'event_cancelled','critical',
                       'Событие отменено', :body, 'event', :event,
                       '/app/event/' || CAST(:event AS text)
                FROM events.waitlist_entries w
                WHERE w.event_id=:event AND w.status='waiting'
                """
            ),
            {"event": str(event_id), "body": CANCEL_REASONS[reason]},
        )
        await connection.execute(
            text(
                """
                UPDATE events.waitlist_entries
                SET status='cancelled',closed_at=now()
                WHERE event_id=:event AND status='waiting'
                """
            ),
            {"event": event_id},
        )


async def create_special_event(
    engine: AsyncEngine,
    *,
    staff_id: UUID,
    city_id: UUID,
    category_id: UUID,
    title: str,
    description: str,
    starts_at: datetime,
    ends_at: datetime,
    place: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
) -> UUID:
    normalized_title = title.strip()
    normalized_description = description.strip()
    normalized_place = place.strip()
    if not 1 <= len(normalized_title) <= 60:
        raise EventManagementError("title_invalid")
    if not 1 <= len(normalized_description) <= 1000:
        raise EventManagementError("description_invalid")
    if (latitude is None) != (longitude is None):
        raise EventManagementError("coordinates_incomplete")
    if ends_at <= starts_at:
        raise EventManagementError("end_must_follow_start")
    if ends_at > starts_at + timedelta(days=7):
        raise EventManagementError("event_too_long")
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=UTC)
    if ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=UTC)

    async with engine.begin() as connection:
        category_available = await connection.scalar(
            text(
                """
                SELECT EXISTS(
                    SELECT 1 FROM discovery.categories
                    WHERE id = :category AND is_active AND slug NOT IN ('special','cinema','music')
                )
                """
            ),
            {"category": category_id},
        )
        if not category_available:
            raise EventManagementError("category_not_available")
        city = (
            (
                await connection.execute(
                    text(
                        """
                        SELECT is_active, name,
                               ST_Y(ST_Centroid(boundary::geometry)) AS center_latitude,
                               ST_X(ST_Centroid(boundary::geometry)) AS center_longitude
                        FROM discovery.cities
                        WHERE id = :city
                        """
                    ),
                    {"city": city_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if city is None or not city["is_active"]:
            raise EventManagementError("city_not_available")
        if latitude is None:
            if city["center_latitude"] is None:
                raise EventManagementError("city_has_no_boundary")
            latitude, longitude = (
                float(city["center_latitude"]),
                float(city["center_longitude"]),
            )

        address = normalized_place or city["name"]
        event_id = uuid4()
        revision_id = uuid4()
        await connection.execute(
            text(
                """
                INSERT INTO events.events
                    (id, kind, event_scope, audit_actor_id, city_id, category_id,
                     lifecycle_status, moderation_status)
                VALUES
                    (:event, 'special', 'community', :staff, :city, :category,
                     'published', 'approved')
                """
            ),
            {
                "event": event_id,
                "staff": staff_id,
                "city": city_id,
                "category": category_id,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO events.event_revisions
                    (id, event_id, revision_number, title, description,
                     starts_at, ends_at, location, normalized_address,
                     street_name, address_visibility, moderation_status,
                     decided_at)
                VALUES
                    (:revision, :event, 1, :title, :description, :starts, :ends,
                     ST_SetSRID(ST_Point(:longitude, :latitude), 4326)::geography,
                     :address, :street, 'exact_public', 'approved', now())
                """
            ),
            {
                "revision": revision_id,
                "event": event_id,
                "title": normalized_title,
                "description": normalized_description,
                "starts": starts_at,
                "ends": ends_at,
                "longitude": longitude,
                "latitude": latitude,
                "address": address,
                "street": address,
            },
        )
        await connection.execute(
            text(
                """
                UPDATE events.events
                SET current_revision_id = :revision,
                    approved_revision_id = :revision
                WHERE id = :event
                """
            ),
            {"revision": revision_id, "event": event_id},
        )
        await connection.execute(
            text(
                """
                INSERT INTO trust_safety.staff_audit_log
                    (id, actor_staff_id, action, result, details)
                VALUES (:id, :staff, 'special_event.create', 'success',
                        jsonb_build_object('event_id', CAST(:event AS text)))
                """
            ),
            {"id": uuid4(), "staff": staff_id, "event": str(event_id)},
        )
    return event_id


async def cancel_special_event(
    engine: AsyncEngine, *, event_id: UUID, staff_id: UUID, reason: CancelReason
) -> None:
    if reason not in CANCEL_REASONS:
        raise EventManagementError("invalid_cancel_reason")
    async with engine.begin() as connection:
        event = await connection.scalar(
            text(
                """
                UPDATE events.events e
                SET lifecycle_status='cancelled', cancellation_reason_code=:reason,
                    cancelled_at=now(), version=version+1, updated_at=now()
                WHERE e.id=:event AND e.kind='special'
                  AND e.lifecycle_status='published'
                  AND EXISTS (
                    SELECT 1 FROM events.event_revisions r
                    WHERE r.id=e.approved_revision_id AND r.ends_at>now()
                  )
                RETURNING id
                """
            ),
            {"event": event_id, "reason": reason},
        )
        if event is None:
            raise EventManagementConflict("event_not_cancellable")
        await connection.execute(
            text(
                """
                INSERT INTO trust_safety.staff_audit_log
                    (id,actor_staff_id,action,result,details)
                VALUES (:id,:staff,'special_event.cancel','success',
                        jsonb_build_object('event_id', CAST(:event AS text),
                                           'reason', CAST(:reason AS text)))
                """
            ),
            {
                "id": uuid4(),
                "staff": staff_id,
                "event": str(event_id),
                "reason": reason,
            },
        )


async def finish_due_events(engine: AsyncEngine) -> int:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                UPDATE trust_safety.event_reviews q
                SET status='rejected', normalized_reason_code='event_finished',
                    decided_at=now()
                FROM events.events e
                JOIN events.event_revisions approved
                  ON approved.id=e.approved_revision_id
                WHERE q.event_id=e.id AND q.status='pending'
                  AND e.lifecycle_status='published' AND approved.ends_at<=now()
                """
            )
        )
        await connection.execute(
            text(
                """
                UPDATE events.event_revisions pending
                SET moderation_status='rejected', decided_at=now()
                FROM events.events e
                JOIN events.event_revisions approved
                  ON approved.id=e.approved_revision_id
                WHERE pending.event_id=e.id AND pending.moderation_status='pending'
                  AND e.lifecycle_status='published' AND approved.ends_at<=now()
                """
            )
        )
        await connection.execute(
            text(
                """
                UPDATE events.waitlist_entries w
                SET status='cancelled',closed_at=now()
                FROM events.events e
                JOIN events.event_revisions r ON r.id=e.approved_revision_id
                WHERE w.event_id=e.id AND w.status='waiting'
                  AND e.lifecycle_status='published' AND r.ends_at<=now()
                """
            )
        )
        result = await connection.execute(
            text(
                """
                UPDATE events.events e
                SET lifecycle_status='finished', moderation_status='approved',
                    version=version+1, updated_at=now()
                FROM events.event_revisions r
                WHERE e.approved_revision_id=r.id
                  AND e.lifecycle_status='published' AND r.ends_at<=now()
                """
            )
        )
    return result.rowcount or 0
