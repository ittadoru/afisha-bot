# ruff: noqa: RUF001 -- the Russian letter "ё" is intentionally normalized.

from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from afishabot.modules.discovery.public.geo import StreetAnchorCandidate
from afishabot.modules.discovery.public.service_area import SERVICE_AREA_RADIUS_METERS


class StreetAnchorError(Exception):
    pass


def street_key(value: str) -> str:
    return " ".join(value.casefold().replace("ё", "е").split())


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
