from collections.abc import Mapping
from typing import Any

import httpx

from afishabot.modules.discovery.public.geo import (
    CanonicalAddress,
    ReverseGeocodingMalformed,
    ReverseGeocodingNotFound,
    ReverseGeocodingUnavailable,
)


class NominatimReverseGeocoder:
    """Private reverse-geocoding adapter; callers never receive provider payloads."""

    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds)

    async def reverse(
        self, *, latitude: float, longitude: float, locale: str
    ) -> CanonicalAddress:
        params: dict[str, str | float | int] = {
            "lat": latitude,
            "lon": longitude,
            "format": "geocodejson",
            "layer": "address",
            "zoom": 18,
            "addressdetails": 1,
        }
        headers = {"Accept-Language": locale, "User-Agent": "AfishaBot/0.1"}

        async with httpx.AsyncClient(
            timeout=self._timeout, follow_redirects=False
        ) as client:
            for attempt in range(2):
                try:
                    response = await client.get(
                        f"{self._base_url}/reverse", params=params, headers=headers
                    )
                    if response.status_code == 404:
                        raise ReverseGeocodingNotFound
                    response.raise_for_status()
                    return self._parse(response.json(), locale)
                except ReverseGeocodingNotFound:
                    raise
                except (
                    httpx.TimeoutException,
                    httpx.TransportError,
                    httpx.HTTPStatusError,
                ) as exc:
                    if attempt == 1:
                        raise ReverseGeocodingUnavailable from exc
                except (TypeError, ValueError) as exc:
                    raise ReverseGeocodingMalformed from exc
        raise ReverseGeocodingUnavailable

    @staticmethod
    def _parse(payload: Any, locale: str) -> CanonicalAddress:
        if not isinstance(payload, Mapping):
            raise ReverseGeocodingMalformed
        features = payload.get("features")
        if not isinstance(features, list) or not features:
            raise ReverseGeocodingNotFound
        first = features[0]
        if not isinstance(first, Mapping):
            raise ReverseGeocodingMalformed
        properties = first.get("properties")
        if not isinstance(properties, Mapping):
            raise ReverseGeocodingMalformed
        geocoding = properties.get("geocoding")
        if not isinstance(geocoding, Mapping):
            raise ReverseGeocodingMalformed

        display_name = NominatimReverseGeocoder._text(geocoding, "label")
        city = NominatimReverseGeocoder._first_text(
            geocoding, "city", "town", "village"
        )
        region = NominatimReverseGeocoder._first_text(geocoding, "state", "county")
        place_id = NominatimReverseGeocoder._first_text(geocoding, "place_id", "osm_id")
        street = NominatimReverseGeocoder._optional_text(geocoding, "street")
        precision = "street" if street else "locality"
        return CanonicalAddress(
            display_name=display_name,
            street=street,
            city=city,
            region=region,
            provider_place_id=place_id,
            locale=locale,
            precision=precision,
        )

    @staticmethod
    def _text(data: Mapping[str, Any], key: str) -> str:
        value = data.get(key)
        if not isinstance(value, (str, int)) or not str(value).strip():
            raise ReverseGeocodingMalformed
        return str(value).strip()

    @staticmethod
    def _first_text(data: Mapping[str, Any], *keys: str) -> str:
        for key in keys:
            value = data.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value).strip()
        raise ReverseGeocodingMalformed

    @staticmethod
    def _optional_text(data: Mapping[str, Any], key: str) -> str | None:
        value = data.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
        return None
