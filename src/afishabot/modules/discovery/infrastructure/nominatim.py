from collections.abc import Mapping
import json
from typing import cast

import httpx

from afishabot.modules.discovery.public.geo import (
    CanonicalAddress,
    StreetAnchorCandidate,
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
                    return self.parse(response.json(), locale)
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

    async def street_anchor(
        self, *, street: str, city: str, locale: str
    ) -> StreetAnchorCandidate:
        params: dict[str, str | int] = {
            "street": street,
            "city": city,
            "format": "geojson",
            "polygon_geojson": 1,
            "limit": 1,
        }
        headers = {"Accept-Language": locale, "User-Agent": "AfishaBot/0.1"}
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, follow_redirects=False
            ) as client:
                response = await client.get(
                    f"{self._base_url}/search", params=params, headers=headers
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
            raise ReverseGeocodingUnavailable from exc
        except (TypeError, ValueError) as exc:
            raise ReverseGeocodingMalformed from exc
        if not isinstance(payload, Mapping):
            raise ReverseGeocodingMalformed
        features = payload.get("features")
        if not isinstance(features, list) or not features:
            raise ReverseGeocodingNotFound
        feature = features[0]
        if not isinstance(feature, Mapping):
            raise ReverseGeocodingMalformed
        geometry = feature.get("geometry")
        properties = feature.get("properties")
        if not isinstance(geometry, Mapping) or not isinstance(properties, Mapping):
            raise ReverseGeocodingMalformed
        geometry_type = geometry.get("type")
        if geometry_type not in {
            "LineString", "MultiLineString", "Polygon", "MultiPolygon"
        }:
            raise ReverseGeocodingNotFound
        place_id = properties.get("place_id") or properties.get("osm_id")
        if not isinstance(place_id, (str, int)):
            raise ReverseGeocodingMalformed
        return StreetAnchorCandidate(
            provider_place_id=str(place_id),
            geometry_geojson=json.dumps(geometry, separators=(",", ":")),
        )

    @staticmethod
    def parse(payload: object, locale: str) -> CanonicalAddress:
        if not isinstance(payload, Mapping):
            raise ReverseGeocodingMalformed
        root = cast(Mapping[str, object], payload)
        features = root.get("features")
        if not isinstance(features, list) or not features:
            raise ReverseGeocodingNotFound
        feature_list = cast(list[object], features)
        first = feature_list[0]
        if not isinstance(first, Mapping):
            raise ReverseGeocodingMalformed
        feature = cast(Mapping[str, object], first)
        properties = feature.get("properties")
        if not isinstance(properties, Mapping):
            raise ReverseGeocodingMalformed
        properties_map = cast(Mapping[str, object], properties)
        geocoding = properties_map.get("geocoding")
        if not isinstance(geocoding, Mapping):
            raise ReverseGeocodingMalformed
        canonical = cast(Mapping[str, object], geocoding)

        display_name = NominatimReverseGeocoder._text(canonical, "label")
        city = NominatimReverseGeocoder._locality(canonical)
        region = NominatimReverseGeocoder._first_text(canonical, "state", "county")
        place_id = NominatimReverseGeocoder._first_text(canonical, "place_id", "osm_id")
        street = NominatimReverseGeocoder._street(canonical)
        house_number = NominatimReverseGeocoder._optional_text(
            canonical, "housenumber"
        )
        precision = "house" if house_number else "street" if street else "locality"
        return CanonicalAddress(
            display_name=display_name,
            street=street,
            house_number=house_number,
            city=city,
            region=region,
            provider_place_id=place_id,
            locale=locale,
            precision=precision,
        )

    @staticmethod
    def _text(data: Mapping[str, object], key: str) -> str:
        value = data.get(key)
        if not isinstance(value, (str, int)) or not str(value).strip():
            raise ReverseGeocodingMalformed
        return str(value).strip()

    @staticmethod
    def _first_text(data: Mapping[str, object], *keys: str) -> str:
        for key in keys:
            value = data.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value).strip()
        raise ReverseGeocodingMalformed

    @staticmethod
    def _locality(data: Mapping[str, object]) -> str:
        """Return a provider locality without accepting arbitrary display names."""
        for key in ("city", "town", "village"):
            value = data.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value).strip()
        kind = data.get("type")
        name = data.get("name")
        if (
            isinstance(kind, str)
            and kind in {"city", "town", "village", "locality"}
            and isinstance(name, (str, int))
            and str(name).strip()
        ):
            return str(name).strip()
        raise ReverseGeocodingMalformed

    @staticmethod
    def _street(data: Mapping[str, object]) -> str | None:
        street = NominatimReverseGeocoder._optional_text(data, "street")
        if street is not None:
            return street
        kind = data.get("type")
        name = data.get("name")
        if (
            isinstance(kind, str)
            and kind in {
                "street", "road", "residential", "service", "pedestrian",
                "living_street", "primary", "secondary", "tertiary",
            }
            and isinstance(name, (str, int))
            and str(name).strip()
        ):
            return str(name).strip()
        return None

    @staticmethod
    def _optional_text(data: Mapping[str, object], key: str) -> str | None:
        value = data.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
        return None
