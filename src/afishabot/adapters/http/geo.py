from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from afishabot.modules.discovery.infrastructure.nominatim import (
    NominatimReverseGeocoder,
)
from afishabot.modules.discovery.public.geo import (
    CanonicalAddress,
    ReverseGeocodingMalformed,
    ReverseGeocodingNotFound,
    ReverseGeocodingUnavailable,
)

router = APIRouter(prefix="/geo", tags=["geo"])


class ReverseGeocodingResponse(BaseModel):
    display_name: str
    street: str | None
    house_number: str | None
    city: str
    region: str
    provider_place_id: str
    locale: str
    precision: str


class CityResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    center_latitude: float
    center_longitude: float


class CategoryResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    is_special: bool
    organizer_selectable: bool


class CatalogResponse(BaseModel):
    cities: list[CityResponse]
    categories: list[CategoryResponse]


def get_reverse_geocoder(request: Request) -> NominatimReverseGeocoder:
    return cast(NominatimReverseGeocoder, request.app.state.reverse_geocoder)


def get_database_engine(request: Request) -> AsyncEngine:
    return cast(AsyncEngine, request.app.state.database_engine)


@router.get("/catalog", response_model=CatalogResponse)
async def catalog(
    engine: Annotated[AsyncEngine, Depends(get_database_engine)],
) -> CatalogResponse:
    async with engine.connect() as connection:
        city_rows = (
            await connection.execute(
                text(
                    """
                    SELECT id, slug, name,
                           ST_Y(ST_PointOnSurface(boundary::geometry)) AS center_latitude,
                           ST_X(ST_PointOnSurface(boundary::geometry)) AS center_longitude
                    FROM discovery.cities
                    WHERE is_active AND boundary IS NOT NULL
                    ORDER BY CASE slug
                        WHEN 'makhachkala' THEN 1
                        WHEN 'khasavyurt' THEN 2
                        WHEN 'derbent' THEN 3
                        ELSE 99
                    END
                    """
                )
            )
        ).mappings()
        category_rows = (
            await connection.execute(
                text(
                    """
                    SELECT id, slug, name, is_special, organizer_selectable
                    FROM discovery.categories
                    WHERE is_active
                    ORDER BY sort_order
                    """
                )
            )
        ).mappings()
        return CatalogResponse(
            cities=[CityResponse.model_validate(row) for row in city_rows],
            categories=[CategoryResponse.model_validate(row) for row in category_rows],
        )


@router.get("/reverse", response_model=ReverseGeocodingResponse)
async def reverse_geocode(
    latitude: Annotated[float, Query(alias="lat", ge=-90, le=90)],
    longitude: Annotated[float, Query(alias="lon", ge=-180, le=180)],
    request: Request,
    geocoder: Annotated[NominatimReverseGeocoder, Depends(get_reverse_geocoder)],
) -> ReverseGeocodingResponse:
    language = request.headers.get("Accept-Language", "ru").split(",", maxsplit=1)[0][
        :16
    ]
    try:
        address: CanonicalAddress = await geocoder.reverse(
            latitude=latitude,
            longitude=longitude,
            locale=language,
        )
    except ReverseGeocodingNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="address_not_found",
        ) from exc
    except (ReverseGeocodingUnavailable, ReverseGeocodingMalformed) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="reverse_geocoding_unavailable",
        ) from exc
    return ReverseGeocodingResponse.model_validate(address, from_attributes=True)


@router.get("/resolve", response_model=ReverseGeocodingResponse)
async def resolve_event_location(
    city_id: Annotated[UUID, Query()],
    latitude: Annotated[float, Query(alias="lat", ge=-90, le=90)],
    longitude: Annotated[float, Query(alias="lon", ge=-180, le=180)],
    request: Request,
    engine: Annotated[AsyncEngine, Depends(get_database_engine)],
    geocoder: Annotated[NominatimReverseGeocoder, Depends(get_reverse_geocoder)],
) -> ReverseGeocodingResponse:
    async with engine.connect() as connection:
        inside = await connection.scalar(
            text(
                """
                SELECT ST_Covers(
                    boundary::geometry,
                    ST_SetSRID(ST_Point(:longitude, :latitude), 4326)
                )
                FROM discovery.cities
                WHERE id = :city_id AND is_active AND boundary IS NOT NULL
                """
            ),
            {"city_id": city_id, "latitude": latitude, "longitude": longitude},
        )
    if inside is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="city_not_supported",
        )
    if not inside:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="point_outside_city",
        )
    return await reverse_geocode(latitude, longitude, request, geocoder)
