from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class PublicEventNotFound(Exception):
    pass


async def event_feed(
    engine: AsyncEngine,
    *,
    city_id: UUID,
    viewer_id: UUID | None,
    view: Literal["list", "map"],
) -> list[dict[str, Any]]:
    if view == "list":
        return await _event_list(engine, city_id=city_id, viewer_id=viewer_id)
    return await _event_map(engine, city_id=city_id, viewer_id=viewer_id)


async def _event_list(
    engine: AsyncEngine, *, city_id: UUID, viewer_id: UUID | None
) -> list[dict[str, Any]]:
    async with engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    """
                    SELECT e.id,e.kind,cat.slug AS category_slug,
                           cat.name AS category,r.title,r.description,
                           r.starts_at,r.ends_at,r.street_name,
                           CASE WHEN r.address_visibility='exact_public'
                                  OR e.creator_user_id=CAST(:viewer AS uuid)
                                  OR (r.address_visibility='exact_participants'
                                      AND EXISTS (
                                        SELECT 1 FROM events.participation_episodes p
                                        WHERE p.event_id=e.id
                                          AND p.user_id=CAST(:viewer AS uuid)
                                          AND p.status='active'))
                                THEN r.normalized_address ELSE r.street_name END
                             AS visible_address,
                           e.capacity,
                           (SELECT count(*) FROM events.participation_episodes p
                            WHERE p.event_id=e.id AND p.status='active')
                             AS participant_count,
                           (SELECT count(*) FROM events.event_interests i
                            WHERE i.event_id=e.id AND i.active) AS interest_count,
                           profile.public_id AS organizer_public_id,
                           profile.display_name AS organizer_name,
                           organizer.status AS organizer_status
                    FROM events.events e
                    JOIN events.event_revisions r ON r.id=e.approved_revision_id
                    JOIN discovery.categories cat ON cat.id=e.category_id
                    LEFT JOIN accounts.profiles profile
                      ON profile.user_id=e.creator_user_id
                    LEFT JOIN reputation.organizer_profiles organizer
                      ON organizer.user_id=e.creator_user_id
                    WHERE e.city_id=:city AND e.lifecycle_status='published'
                      AND r.ends_at>now()
                    ORDER BY (e.kind='special') DESC,r.starts_at,e.id
                    LIMIT 200
                    """
                ),
                {"city": city_id, "viewer": viewer_id},
            )
        ).mappings().all()
    return [_with_photo(dict(row)) for row in rows]


async def _event_map(
    engine: AsyncEngine, *, city_id: UUID, viewer_id: UUID | None
) -> list[dict[str, Any]]:
    async with engine.connect() as connection:
        exact = (
            await connection.execute(
                text(
                    """
                    SELECT 'event' AS marker_type,e.id,e.kind,
                           cat.slug AS category_slug,cat.name AS category,
                           r.title,r.starts_at,
                           ST_Y(r.location::geometry) AS latitude,
                           ST_X(r.location::geometry) AS longitude,
                           NULL::text AS street_name,NULL::bigint AS event_count,
                           NULL::uuid[] AS event_ids
                    FROM events.events e
                    JOIN events.event_revisions r ON r.id=e.approved_revision_id
                    JOIN discovery.categories cat ON cat.id=e.category_id
                    WHERE e.city_id=:city AND e.lifecycle_status='published'
                      AND r.ends_at>now()
                      AND (r.address_visibility='exact_public'
                        OR e.creator_user_id=CAST(:viewer AS uuid)
                        OR (r.address_visibility='exact_participants' AND EXISTS (
                          SELECT 1 FROM events.participation_episodes p
                          WHERE p.event_id=e.id
                            AND p.user_id=CAST(:viewer AS uuid)
                            AND p.status='active')))
                    ORDER BY (e.kind='special') DESC,r.starts_at,e.id
                    """
                ),
                {"city": city_id, "viewer": viewer_id},
            )
        ).mappings().all()
        streets = (
            await connection.execute(
                text(
                    """
                    SELECT 'street' AS marker_type,NULL::uuid AS id,
                           'regular'::text AS kind,NULL::text AS category_slug,
                           NULL::text AS category,NULL::text AS title,
                           min(r.starts_at) AS starts_at,
                           ST_Y(a.anchor::geometry) AS latitude,
                           ST_X(a.anchor::geometry) AS longitude,
                           a.display_name AS street_name,count(*) AS event_count,
                           array_agg(e.id ORDER BY (e.kind='special') DESC,
                                     r.starts_at,e.id) AS event_ids
                    FROM events.events e
                    JOIN events.event_revisions r ON r.id=e.approved_revision_id
                    JOIN discovery.street_anchors a ON a.id=r.street_anchor_id
                    WHERE e.city_id=:city AND e.lifecycle_status='published'
                      AND r.ends_at>now()
                      AND NOT (r.address_visibility='exact_public'
                        OR e.creator_user_id=CAST(:viewer AS uuid)
                        OR (r.address_visibility='exact_participants' AND EXISTS (
                          SELECT 1 FROM events.participation_episodes p
                          WHERE p.event_id=e.id
                            AND p.user_id=CAST(:viewer AS uuid)
                            AND p.status='active')))
                    GROUP BY a.id,a.display_name,a.anchor
                    ORDER BY min(r.starts_at),a.id
                    """
                ),
                {"city": city_id, "viewer": viewer_id},
            )
        ).mappings().all()
    return [dict(row) for row in [*exact, *streets]]


async def event_detail(
    engine: AsyncEngine, *, event_id: UUID, viewer_id: UUID | None
) -> dict[str, Any]:
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    """
                    SELECT e.id,e.kind,e.lifecycle_status,
                           e.cancellation_reason_code,e.capacity,
                           cat.slug AS category_slug,cat.name AS category,
                           city.name AS city,r.title,r.description,
                           r.starts_at,r.ends_at,r.street_name,
                           CASE WHEN e.lifecycle_status='published'
                                AND r.ends_at>now() AND
                                (r.address_visibility='exact_public'
                                  OR e.creator_user_id=CAST(:viewer AS uuid)
                                  OR (r.address_visibility='exact_participants'
                                      AND EXISTS (
                                        SELECT 1 FROM events.participation_episodes p
                                        WHERE p.event_id=e.id
                                          AND p.user_id=CAST(:viewer AS uuid)
                                          AND p.status='active')))
                                THEN r.normalized_address ELSE r.street_name END
                             AS visible_address,
                           CASE WHEN e.lifecycle_status='published'
                                AND r.ends_at>now() AND
                                (r.address_visibility='exact_public'
                                  OR e.creator_user_id=CAST(:viewer AS uuid)
                                  OR (r.address_visibility='exact_participants'
                                      AND EXISTS (
                                        SELECT 1 FROM events.participation_episodes p
                                        WHERE p.event_id=e.id
                                          AND p.user_id=CAST(:viewer AS uuid)
                                          AND p.status='active')))
                                THEN ST_Y(r.location::geometry) END AS latitude,
                           CASE WHEN e.lifecycle_status='published'
                                AND r.ends_at>now() AND
                                (r.address_visibility='exact_public'
                                  OR e.creator_user_id=CAST(:viewer AS uuid)
                                  OR (r.address_visibility='exact_participants'
                                      AND EXISTS (
                                        SELECT 1 FROM events.participation_episodes p
                                        WHERE p.event_id=e.id
                                          AND p.user_id=CAST(:viewer AS uuid)
                                          AND p.status='active')))
                                THEN ST_X(r.location::geometry) END AS longitude,
                           (SELECT count(*) FROM events.participation_episodes p
                            WHERE p.event_id=e.id AND p.status='active')
                             AS participant_count,
                           (SELECT count(*) FROM events.event_interests i
                            WHERE i.event_id=e.id AND i.active) AS interest_count,
                           EXISTS (
                             SELECT 1 FROM events.event_interests i
                             WHERE i.event_id=e.id
                               AND i.user_id=CAST(:viewer AS uuid) AND i.active
                           ) AS viewer_interested,
                           (e.creator_user_id=CAST(:viewer AS uuid)) AS viewer_is_organizer,
                           CASE
                             WHEN EXISTS (
                               SELECT 1 FROM events.participation_episodes p
                               WHERE p.event_id=e.id
                                 AND p.user_id=CAST(:viewer AS uuid)
                                 AND p.status='active') THEN 'participating'
                             WHEN EXISTS (
                               SELECT 1 FROM events.waitlist_entries w
                               WHERE w.event_id=e.id
                                 AND w.user_id=CAST(:viewer AS uuid)
                                 AND w.status='waiting') THEN 'waitlisted'
                             WHEN EXISTS (
                               SELECT 1 FROM events.participation_episodes p
                               WHERE p.event_id=e.id
                                 AND p.user_id=CAST(:viewer AS uuid)
                                 AND p.status='excluded') THEN 'excluded'
                             ELSE 'none'
                           END AS viewer_membership,
                           CASE WHEN EXISTS (
                             SELECT 1 FROM events.waitlist_entries mine
                             WHERE mine.event_id=e.id
                               AND mine.user_id=CAST(:viewer AS uuid)
                               AND mine.status='waiting'
                           ) THEN (
                             SELECT count(*) FROM events.waitlist_entries ahead
                             WHERE ahead.event_id=e.id AND ahead.status='waiting'
                               AND ahead.queue_order <= (
                                 SELECT mine.queue_order
                                 FROM events.waitlist_entries mine
                                 WHERE mine.event_id=e.id
                                   AND mine.user_id=CAST(:viewer AS uuid)
                                   AND mine.status='waiting'
                               )
                           ) END AS queue_position,
                           profile.public_id AS organizer_public_id,
                           profile.display_name AS organizer_name,
                           organizer.status AS organizer_status
                    FROM events.events e
                    JOIN events.event_revisions r ON r.id=e.approved_revision_id
                    JOIN discovery.categories cat ON cat.id=e.category_id
                    JOIN discovery.cities city ON city.id=e.city_id
                    LEFT JOIN accounts.profiles profile
                      ON profile.user_id=e.creator_user_id
                    LEFT JOIN reputation.organizer_profiles organizer
                      ON organizer.user_id=e.creator_user_id
                    WHERE e.id=:event
                      AND e.lifecycle_status IN ('published','finished','cancelled')
                    """
                ),
                {"event": event_id, "viewer": viewer_id},
            )
        ).mappings().one_or_none()
    if row is None:
        raise PublicEventNotFound
    return _with_photo(dict(row))


async def event_photo_key(engine: AsyncEngine, event_id: UUID) -> str:
    async with engine.connect() as connection:
        key = await connection.scalar(
            text(
                """
                SELECT a.storage_key
                FROM events.events e
                JOIN events.event_photos ep
                  ON ep.revision_id=e.approved_revision_id AND ep.position=1
                JOIN media.assets a ON a.id=ep.media_asset_id AND a.state='ready'
                WHERE e.id=:event
                  AND e.lifecycle_status IN ('published','finished','cancelled')
                """
            ),
            {"event": event_id},
        )
    if key is None:
        raise PublicEventNotFound
    return key


def _with_photo(row: dict[str, Any]) -> dict[str, Any]:
    row["photo_url"] = f"/api/events/{row['id']}/photo"
    capacity = row.get("capacity")
    participants = int(row.get("participant_count") or 0)
    row["available_places"] = None if capacity is None else max(0, capacity - participants)
    return row
