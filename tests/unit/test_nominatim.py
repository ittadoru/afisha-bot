import pytest

from afishabot.modules.discovery.infrastructure.nominatim import (
    NominatimReverseGeocoder,
)
from afishabot.modules.discovery.public.geo import ReverseGeocodingMalformed


def test_nominatim_parses_only_canonical_fields() -> None:
    result = NominatimReverseGeocoder._parse(
        {
            "features": [
                {
                    "properties": {
                        "geocoding": {
                            "label": (
                                "улица Дахадаева, Махачкала"
                            ),
                            "street": "улица Дахадаева",
                            "city": "Махачкала",
                            "state": "Республика Дагестан",
                            "osm_id": 123,
                            "untrusted_extra": "must not escape",
                        }
                    }
                }
            ]
        },
        "ru",
    )

    assert result.street == "улица Дахадаева"
    assert result.provider_place_id == "123"
    assert not hasattr(result, "untrusted_extra")


def test_nominatim_rejects_malformed_payload() -> None:
    with pytest.raises(ReverseGeocodingMalformed):
        NominatimReverseGeocoder._parse({"features": [{}]}, "ru")
