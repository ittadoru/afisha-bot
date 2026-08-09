# ruff: noqa: RUF001 -- the Russian letter "ё" is intentionally normalized.

from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from afishabot.modules.discovery.public.geo import StreetAnchorCandidate
from afishabot.modules.discovery.public.service_area import SERVICE_AREA_RADIUS_METERS


class StreetAnchorError(Exception):
    pass


def street_key(value: str) -> str:
    normalized = " ".join(value.casefold().replace("ё", "е").split())
    for prefix in ("улица ", "ул. ", "ул "):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    return normalized


async def create_staff_street_anchor_in_transaction(
    connection: AsyncConnection,
    *,
    city_id: UUID,
    display_name: str,
    latitude: float,
    longitude: float,
) -> UUID:
    """Create one approximate staff-controlled point without touching an existing one."""
    key = street_key(display_name)
    if not key:
        raise StreetAnchorError("street_anchor_name_invalid")
    row = await connection.scalar(
        text(
            """
            WITH valid AS (
              SELECT ST_SetSRID(ST_Point(:longitude, :latitude),4326)::geography AS point
              FROM discovery.cities c
              WHERE c.id=:city AND ST_DWithin(
                c.boundary,
                ST_SetSRID(ST_Point(:longitude, :latitude),4326)::geography,
                :radius_meters
              )
            )
            INSERT INTO discovery.street_anchors
              (id, city_id, street_key, display_name, provider_place_id, source, anchor)
            SELECT :id, :city, :key, :display, NULL, 'staff', point FROM valid
            ON CONFLICT (city_id, street_key) DO NOTHING
            RETURNING id
            """
        ),
        {"id": uuid4(), "city": city_id, "key": key, "display": display_name.strip(),
         "latitude": latitude, "longitude": longitude,
         "radius_meters": SERVICE_AREA_RADIUS_METERS},
    )
    if row is not None:
        return row
    exists = await connection.scalar(
        text("SELECT id FROM discovery.street_anchors WHERE city_id=:city AND street_key=:key"),
        {"city": city_id, "key": key},
    )
    if exists is not None:
        raise StreetAnchorError("street_anchor_exists")
    raise StreetAnchorError("street_anchor_outside_city")


async def save_street_anchor(
    engine: AsyncEngine,
    *,
    city_id: UUID,
    street: str,
    candidate: StreetAnchorCandidate,
) -> UUID:
    async with engine.begin() as connection:
        return await save_street_anchor_in_transaction(
            connection,
            city_id=city_id,
            street=street,
            candidate=candidate,
        )


async def save_street_anchor_in_transaction(
    connection: AsyncConnection,
    *,
    city_id: UUID,
    street: str,
    candidate: StreetAnchorCandidate,
) -> UUID:
    anchor_id = uuid4()
    row = await connection.scalar(
        text(
            """
            WITH source AS (
              SELECT ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326) AS geometry
            ), candidate AS (
              SELECT ST_PointOnSurface(ST_CollectionExtract(
                         ST_MakeValid(geometry),
                         CASE WHEN GeometryType(geometry) IN
                           ('LINESTRING','MULTILINESTRING') THEN 2 ELSE 3 END
                       )) AS point
              FROM source
            ), valid AS (
              SELECT point FROM candidate
              JOIN discovery.cities c ON c.id=:city
              WHERE NOT ST_IsEmpty(point)
                AND ST_DWithin(
                    c.boundary,
                    point::geography,
                    :radius_meters
                )
            )
            INSERT INTO discovery.street_anchors
                (id,city_id,street_key,display_name,provider_place_id,anchor)
            SELECT :id,:city,:key,:display,:provider,point::geography FROM valid
            ON CONFLICT (city_id,street_key) DO UPDATE SET
                display_name=EXCLUDED.display_name,
                provider_place_id=EXCLUDED.provider_place_id,
                anchor=EXCLUDED.anchor,
                geometry_version=discovery.street_anchors.geometry_version+1,
                updated_at=now()
            RETURNING id
            """
        ),
        {
            "geometry": candidate.geometry_geojson,
            "city": city_id,
            "id": anchor_id,
            "key": street_key(street),
            "display": street.strip(),
            "provider": candidate.provider_place_id,
            "radius_meters": SERVICE_AREA_RADIUS_METERS,
        },
    )
    if row is None:
        raise StreetAnchorError("street_anchor_outside_city")
    return row
