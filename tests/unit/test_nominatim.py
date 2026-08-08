from typing import cast

import httpx
import pytest

from afishabot.modules.discovery.infrastructure.nominatim import (
    NominatimReverseGeocoder,
)
from afishabot.modules.discovery.public.geo import (
    ReverseGeocodingMalformed,
    ReverseGeocodingNotFound,
    ReverseGeocodingUnavailable,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://nominatim.test/reverse")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                "provider error", request=request, response=response
            )

    def json(self) -> object:
        return self._payload


class FakeClient:
    def __init__(self, outcomes: list[FakeResponse | Exception]) -> None:
        self.outcomes = outcomes
        self.calls = 0

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> None:
        return None

    async def get(self, url: str, **kwargs: object) -> FakeResponse:
        del url, kwargs
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def install_fake_client(monkeypatch: pytest.MonkeyPatch, client: FakeClient) -> None:
    def create_client(*args: object, **kwargs: object) -> FakeClient:
        del args, kwargs
        return client

    monkeypatch.setattr(httpx, "AsyncClient", create_client)


def canonical_payload() -> object:
    return {
        "features": [
            {
                "properties": {
                    "geocoding": {
                        "label": "улица Дахадаева, Махачкала",
                        "street": "улица Дахадаева",
                        "city": "Махачкала",
                        "state": "Республика Дагестан",
                        "osm_id": 123,
                    }
                }
            }
        ]
    }


def test_nominatim_parses_only_canonical_fields() -> None:
    result = NominatimReverseGeocoder.parse(
        {
            "features": [
                {
                    "properties": {
                        "geocoding": {
                            "label": ("улица Дахадаева, Махачкала"),
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
    assert result.house_number is None
    assert result.provider_place_id == "123"
    assert not hasattr(result, "untrusted_extra")


def test_nominatim_parses_a_city_feature_without_a_street() -> None:
    result = NominatimReverseGeocoder.parse(
        {
            "features": [{"properties": {"geocoding": {
                "label": "Хасавюрт, Дагестан, Россия",
                "name": "Хасавюрт", "type": "city", "state": "Дагестан", "osm_id": 1,
            }}}]
        },
        "ru",
    )
    assert result.city == "Хасавюрт"
    assert result.street is None
    assert result.precision == "locality"


def test_nominatim_uses_address_feature_name_for_street_and_house() -> None:
    result = NominatimReverseGeocoder.parse(
        {
            "features": [{"properties": {"geocoding": {
                "label": "улица Гагарина, Дербент, Дагестан, Россия",
                "type": "street", "name": "улица Гагарина",
                "city": "Дербент", "state": "Дагестан", "osm_id": 42,
            }}}]
        },
        "ru",
    )
    assert result.street == "улица Гагарина"
    assert result.house_number is None
    assert result.precision == "street"

    house = NominatimReverseGeocoder.parse(
        {
            "features": [{"properties": {"geocoding": {
                "label": "3, улица Фурманова, Махачкала, Дагестан, Россия",
                "street": "улица Фурманова", "housenumber": "3",
                "city": "Махачкала", "state": "Дагестан", "osm_id": 43,
            }}}]
        },
        "ru",
    )
    assert house.house_number == "3"
    assert house.precision == "house"


def test_nominatim_rejects_an_arbitrary_name_as_a_city() -> None:
    with pytest.raises(ReverseGeocodingMalformed):
        NominatimReverseGeocoder.parse(
            {"features": [{"properties": {"geocoding": {
                "label": "Неизвестное место", "name": "Неизвестное место",
                "type": "house", "state": "Дагестан", "osm_id": 1,
            }}}]},
            "ru",
        )


def test_nominatim_rejects_malformed_payload() -> None:
    payload = cast(object, {"features": [{}]})
    with pytest.raises(ReverseGeocodingMalformed):
        NominatimReverseGeocoder.parse(payload, "ru")


async def test_nominatim_reverse_returns_canonical_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeClient([FakeResponse(200, canonical_payload())])
    install_fake_client(monkeypatch, client)

    result = await NominatimReverseGeocoder("https://nominatim.test", 1).reverse(
        latitude=42.98,
        longitude=47.50,
        locale="ru",
    )

    assert result.city == "Махачкала"
    assert client.calls == 1


async def test_nominatim_reverse_does_not_retry_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeClient([FakeResponse(404, {})])
    install_fake_client(monkeypatch, client)

    with pytest.raises(ReverseGeocodingNotFound):
        await NominatimReverseGeocoder("https://nominatim.test", 1).reverse(
            latitude=42.98,
            longitude=47.50,
            locale="ru",
        )

    assert client.calls == 1


async def test_nominatim_reverse_retries_temporary_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeClient(
        [
            httpx.ConnectTimeout("timeout"),
            httpx.ConnectTimeout("timeout"),
        ]
    )
    install_fake_client(monkeypatch, client)

    with pytest.raises(ReverseGeocodingUnavailable):
        await NominatimReverseGeocoder("https://nominatim.test", 1).reverse(
            latitude=42.98,
            longitude=47.50,
            locale="ru",
        )

    assert client.calls == 2


async def test_nominatim_reverse_rejects_malformed_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeClient([FakeResponse(200, "not-an-object")])
    install_fake_client(monkeypatch, client)

    with pytest.raises(ReverseGeocodingMalformed):
        await NominatimReverseGeocoder("https://nominatim.test", 1).reverse(
            latitude=42.98,
            longitude=47.50,
            locale="ru",
        )
