from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from afishabot.modules.discovery.public.geo import CanonicalAddress

AddressVisibility = Literal["street_only", "exact_participants", "exact_public"]


class EventCreationError(Exception):
    pass


class EventCreationConflict(EventCreationError):
    pass


@dataclass(frozen=True, slots=True)
class CreateEventCommand:
    user_id: UUID
    idempotency_key: UUID
    request_fingerprint: str
    title: str
    description: str
    category_id: UUID
    city_id: UUID
    starts_at: datetime
    ends_at: datetime
    capacity: int | None
    latitude: float
    longitude: float
    address_visibility: AddressVisibility
    location_note: str | None
    photo_upload_id: UUID
    canonical_address: CanonicalAddress
    street_anchor_id: UUID | None = None
    source_looking_post_id: UUID | None = None
    source_looking_post_version: int | None = None


@dataclass(frozen=True, slots=True)
class CreatedEvent:
    event_id: UUID
    publication_status: Literal["published", "pending_review"]


async def find_created_event(
    engine: AsyncEngine,
    *,
    user_id: UUID,
    idempotency_key: UUID,
    request_fingerprint: str,
) -> CreatedEvent | None:
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    """
                    SELECT r.request_fingerprint, r.event_id, e.lifecycle_status
                    FROM events.creation_requests r
                    JOIN events.events e ON e.id=r.event_id
                    WHERE r.user_id=:user AND r.idempotency_key=:key
                      AND e.creator_user_id=:user
                    """
                ),
                {"user": user_id, "key": idempotency_key},
            )
        ).mappings().one_or_none()
    if row is None:
        return None
    if row["request_fingerprint"] != request_fingerprint:
        raise EventCreationConflict("idempotency_key_reused")
    return CreatedEvent(
        event_id=row["event_id"],
        publication_status=(
            "published"
            if row["lifecycle_status"] == "published"
            else "pending_review"
        ),
    )


async def create_event(
    engine: AsyncEngine, command: CreateEventCommand
) -> CreatedEvent:
    now = datetime.now(UTC)
    if command.ends_at <= command.starts_at:
        raise EventCreationError("end_must_follow_start")
    if command.ends_at > command.starts_at + timedelta(days=7):
        raise EventCreationError("event_too_long")
    if command.capacity is not None and command.capacity < 3:
        raise EventCreationError("capacity_too_small")
    if (command.source_looking_post_id is None) != (command.source_looking_post_version is None):
        raise EventCreationError("looking_post_source_incomplete")

    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:value, 0))"),
            {"value": f"{command.user_id}:{command.idempotency_key}"},
        )
        previous = (
            await connection.execute(
                text(
                    """
                    SELECT request_fingerprint, event_id
                    FROM events.creation_requests
                    WHERE user_id=:user AND idempotency_key=:key
                    """
                ),
                {"user": command.user_id, "key": command.idempotency_key},
            )
        ).mappings().one_or_none()
        if previous is not None:
            if previous["request_fingerprint"] != command.request_fingerprint:
                raise EventCreationConflict("idempotency_key_reused")
            status = await connection.scalar(
                text(
                    "SELECT lifecycle_status FROM events.events "
                    "WHERE id=:event AND creator_user_id=:user"
                ),
                {"event": previous["event_id"], "user": command.user_id},
            )
            return CreatedEvent(
                event_id=previous["event_id"],
                publication_status=(
                    "published" if status == "published" else "pending_review"
                ),
            )

        if command.source_looking_post_id is not None:
            source = (
                await connection.execute(
                    text(
                        """
                        SELECT author_user_id, city_id, category_id, status, version, pending_event_id
                        FROM discovery.looking_posts WHERE id=:post FOR UPDATE
                        """
                    ),
                    {"post": command.source_looking_post_id},
                )
            ).mappings().one_or_none()
            if source is None or source["author_user_id"] != command.user_id:
                raise EventCreationError("looking_post_not_available")
            if source["status"] != "active" or source["pending_event_id"] is not None:
                raise EventCreationConflict("looking_post_conversion_pending")
            if source["version"] != command.source_looking_post_version:
                raise EventCreationConflict("looking_post_stale")
            if source["city_id"] != command.city_id or source["category_id"] != command.category_id:
                raise EventCreationError("looking_post_source_mismatch")

        organizer_status = await connection.scalar(
            text(
                """
                SELECT o.status
                FROM reputation.organizer_profiles o
                JOIN accounts.users u ON u.id=o.user_id AND u.status='active'
                    AND u.accepted_age_rule_at IS NOT NULL
                JOIN accounts.profiles p ON p.user_id=u.id
                WHERE o.user_id=:user AND p.selected_city_id=:city
                """
            ),
            {"user": command.user_id, "city": command.city_id},
        )
        if organizer_status not in {"new", "trusted"}:
            raise EventCreationError("organizer_not_eligible")
        minimum_notice = timedelta(hours=1 if organizer_status == "trusted" else 6)
        if command.starts_at < now + minimum_notice:
            raise EventCreationError(
                "start_too_soon_trusted"
                if organizer_status == "trusted"
                else "start_too_soon_new"
            )

        valid_category = await connection.scalar(
            text(
                """
                SELECT 1 FROM discovery.categories
                WHERE id=:category AND is_active AND organizer_selectable
                  AND NOT is_special
                """
            ),
            {"category": command.category_id},
        )
        if valid_category is None:
            raise EventCreationError("category_not_available")
        inside_city = await connection.scalar(
            text(
                """
                SELECT ST_Covers(
                    boundary::geometry,
                    ST_SetSRID(ST_Point(:longitude, :latitude), 4326)
                )
                FROM discovery.cities
                WHERE id=:city AND is_active AND boundary IS NOT NULL
                """
            ),
            {
                "city": command.city_id,
                "latitude": command.latitude,
                "longitude": command.longitude,
            },
        )
        if inside_city is None:
            raise EventCreationError("city_not_available")
        if not inside_city:
            raise EventCreationError("point_outside_city")
        if (
            command.canonical_address.street is None
            and command.address_visibility != "exact_public"
        ):
            raise EventCreationError("street_required_for_hidden_address")
        if (
            command.address_visibility != "exact_public"
            and command.street_anchor_id is None
        ):
            raise EventCreationError("street_anchor_required")

        photo = (
            await connection.execute(
                text(
                    """
                    SELECT id FROM media.assets
                    WHERE id=:photo AND owner_user_id=:user
                      AND purpose='event_photo' AND state='ready'
                      AND delete_after > now()
                      AND NOT EXISTS (
                          SELECT 1 FROM events.event_photos ep
                          WHERE ep.media_asset_id=media.assets.id
                      )
                    FOR UPDATE
                    """
                ),
                {"photo": command.photo_upload_id, "user": command.user_id},
            )
        ).scalar_one_or_none()
        if photo is None:
            raise EventCreationError("photo_not_available")

        event_id = uuid4()
        revision_id = uuid4()
        published = organizer_status == "trusted"
        event_status = "published" if published else "pending"
        moderation_status = "approved" if published else "pending"
        await connection.execute(
            text(
                """
                INSERT INTO events.events
                    (id, kind, creator_user_id, audit_actor_id, city_id,
                     category_id, lifecycle_status, moderation_status, capacity,
                     current_revision_id, approved_revision_id)
                VALUES
                    (:event, 'regular', :user, :user, :city, :category,
                     :lifecycle, :moderation, :capacity, NULL, NULL)
                """
            ),
            {
                "event": event_id,
                "user": command.user_id,
                "city": command.city_id,
                "category": command.category_id,
                "lifecycle": event_status,
                "moderation": moderation_status,
                "capacity": command.capacity,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO events.event_revisions
                    (id, event_id, revision_number, title, description, landmark,
                     starts_at, ends_at, location, normalized_address,
                     street_name, address_visibility, street_anchor_id,
                     moderation_status,
                     decided_at)
                VALUES
                    (:revision, :event, 1, :title, :description, :location_note, :starts, :ends,
                     ST_SetSRID(ST_Point(:longitude, :latitude), 4326)::geography,
                     :address, :street, :visibility, :street_anchor,
                     :moderation,
                     CASE WHEN :published THEN now() ELSE NULL END)
                """
            ),
            {
                "revision": revision_id,
                "event": event_id,
                "title": command.title,
                "description": command.description,
                "location_note": command.location_note,
                "starts": command.starts_at,
                "ends": command.ends_at,
                "longitude": command.longitude,
                "latitude": command.latitude,
                "address": command.canonical_address.display_name,
                "street": command.canonical_address.street
                or command.canonical_address.city,
                "visibility": command.address_visibility,
                "street_anchor": command.street_anchor_id,
                "moderation": moderation_status,
                "published": published,
            },
        )
        await connection.execute(
            text(
                """
                UPDATE events.events
                SET current_revision_id=:revision,
                    approved_revision_id=CASE
                      WHEN :published THEN CAST(:revision AS uuid) ELSE NULL END
                WHERE id=:event
                """
            ),
            {"revision": revision_id, "published": published, "event": event_id},
        )
        await connection.execute(
            text(
                """
                INSERT INTO events.event_photos
                    (id, event_id, revision_id, media_asset_id, position)
                VALUES (:id, :event, :revision, :asset, 1)
                """
            ),
            {
                "id": uuid4(),
                "event": event_id,
                "revision": revision_id,
                "asset": command.photo_upload_id,
            },
        )
        await connection.execute(
            text(
                "UPDATE media.assets SET delete_after=NULL, updated_at=now() "
                "WHERE id=:asset"
            ),
            {"asset": command.photo_upload_id},
        )
        if not published:
            await connection.execute(
                text(
                    """
                    INSERT INTO trust_safety.event_reviews
                        (id, event_id, event_revision_id, submitted_by_user_id)
                    VALUES (:id, :event, :revision, :user)
                    """
                ),
                {
                    "id": uuid4(),
                    "event": event_id,
                    "revision": revision_id,
                    "user": command.user_id,
                },
            )
        if command.source_looking_post_id is not None:
            if published:
                await connection.execute(
                    text(
                        """
                        UPDATE discovery.looking_posts
                        SET status='converted', converted_event_id=:event, closed_at=now(),
                            delete_after=now()+interval '24 hours', version=version+1
                        WHERE id=:post AND status='active'
                        """
                    ),
                    {"post": command.source_looking_post_id, "event": event_id},
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
                    {"post": command.source_looking_post_id, "event": event_id},
                )
            else:
                await connection.execute(
                    text("UPDATE discovery.looking_posts SET pending_event_id=:event, version=version+1 WHERE id=:post"),
                    {"post": command.source_looking_post_id, "event": event_id},
                )
        await connection.execute(
            text(
                """
                INSERT INTO events.creation_requests
                    (user_id, idempotency_key, request_fingerprint, event_id)
                VALUES (:user, :key, :fingerprint, :event)
                """
            ),
            {
                "user": command.user_id,
                "key": command.idempotency_key,
                "fingerprint": command.request_fingerprint,
                "event": event_id,
            },
        )
    return CreatedEvent(
        event_id=event_id,
        publication_status="published" if published else "pending_review",
    )
