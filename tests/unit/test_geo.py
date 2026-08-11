from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request
from httpx import ASGITransport, AsyncClient

from afishabot.adapters.http.geo import reverse_geocode
from afishabot.app import create_app
from afishabot.core.config import Settings
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
        house_number=None,
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


async def test_catalog_returns_city_service_areas(settings: Settings) -> None:
    city_id = uuid4()
    city_rows = [
        {
            "id": city_id,
            "slug": "makhachkala",
            "name": "Махачкала",
            "center_latitude": 42.98,
            "center_longitude": 47.50,
            "west": 47.1,
            "south": 42.7,
            "east": 47.8,
            "north": 43.3,
            "allowed_area": '{"type":"Polygon","coordinates":[]}',
        }
    ]
    category_rows = [
        {
            "id": uuid4(),
            "slug": "sport",
            "name": "Спорт",
            "is_special": False,
            "organizer_selectable": True,
        }
    ]
    connection = SimpleNamespace(execute=AsyncMock(side_effect=[
        SimpleNamespace(mappings=lambda: city_rows),
        SimpleNamespace(mappings=lambda: category_rows),
    ]))

    @asynccontextmanager
    async def connect() -> object:
        yield connection

    app = create_app(settings)
    app.state.database_engine = SimpleNamespace(connect=connect)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/geo/catalog")

    assert response.status_code == 200
    city = response.json()["cities"][0]
    assert city["id"] == str(city_id)
    assert city["service_radius_m"] == 1_000
    assert city["map_bounds"] == {
        "west": 47.1,
        "south": 42.7,
        "east": 47.8,
        "north": 43.3,
    }
    assert city["allowed_area"] == {"type": "Polygon", "coordinates": []}
    assert connection.execute.await_args_list[0].args[1] == {"radius_meters": 1_000}
