from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Request

from afishabot.adapters.http.geo import reverse_geocode
from afishabot.modules.discovery.infrastructure.nominatim import (
    NominatimReverseGeocoder,
)
from afishabot.modules.discovery.public.geo import (
    CanonicalAddress,
    ReverseGeocodingMalformed,
    ReverseGeocodingNotFound,
    ReverseGeocodingUnavailable,
)


def request_with_language(language: str) -> Request:
    return cast(Request, SimpleNamespace(headers={"Accept-Language": language}))


def geocoder_returning(value: object) -> NominatimReverseGeocoder:
    return cast(
        NominatimReverseGeocoder,
        SimpleNamespace(reverse=AsyncMock(return_value=value)),
    )


def geocoder_raising(error: Exception) -> NominatimReverseGeocoder:
    return cast(
        NominatimReverseGeocoder,
        SimpleNamespace(reverse=AsyncMock(side_effect=error)),
    )


async def test_reverse_geo_returns_canonical_projection() -> None:
    address = CanonicalAddress(
        display_name="улица Дахадаева, Махачкала",
        street="улица Дахадаева",
        city="Махачкала",
        region="Республика Дагестан",
        provider_place_id="123",
        locale="ru",
        precision="street",
    )

    response = await reverse_geocode(
        latitude=42.98,
        longitude=47.50,
        request=request_with_language("ru-RU,ru;q=0.9"),
        geocoder=geocoder_returning(address),
    )

    assert response.city == "Махачкала"
    assert response.locale == "ru"


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (ReverseGeocodingNotFound(), 404, "address_not_found"),
        (ReverseGeocodingUnavailable(), 503, "reverse_geocoding_unavailable"),
        (ReverseGeocodingMalformed(), 503, "reverse_geocoding_unavailable"),
    ],
)
async def test_reverse_geo_maps_provider_errors(
    error: Exception, status_code: int, detail: str
) -> None:
    with pytest.raises(HTTPException) as captured:
        await reverse_geocode(
            latitude=42.98,
            longitude=47.50,
            request=request_with_language("ru"),
            geocoder=geocoder_raising(error),
        )

    assert captured.value.status_code == status_code
    assert captured.value.detail == detail
