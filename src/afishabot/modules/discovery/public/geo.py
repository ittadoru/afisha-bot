from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CanonicalAddress:
    display_name: str
    street: str | None
    house_number: str | None
    city: str
    region: str
    provider_place_id: str
    locale: str
    precision: str


@dataclass(frozen=True, slots=True)
class StreetAnchorCandidate:
    provider_place_id: str
    geometry_geojson: str


class ReverseGeocodingError(Exception):
    """Base error whose details must not be exposed at the HTTP boundary."""


class ReverseGeocodingUnavailable(ReverseGeocodingError):
    pass


class ReverseGeocodingNotFound(ReverseGeocodingError):
    pass


class ReverseGeocodingMalformed(ReverseGeocodingError):
    pass
