from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

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
    city: str
    region: str
    provider_place_id: str
    locale: str
    precision: str


def get_reverse_geocoder(request: Request) -> NominatimReverseGeocoder:
    return cast(NominatimReverseGeocoder, request.app.state.reverse_geocoder)


@router.get("/reverse", response_model=ReverseGeocodingResponse)
async def reverse_geocode(
    latitude: Annotated[float, Query(alias="lat", ge=-90, le=90)],
    longitude: Annotated[float, Query(alias="lon", ge=-180, le=180)],
    request: Request,
    geocoder: Annotated[NominatimReverseGeocoder, Depends(get_reverse_geocoder)],
) -> ReverseGeocodingResponse:
    language = request.headers.get("Accept-Language", "ru").split(
        ",", maxsplit=1
    )[0][:16]
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
