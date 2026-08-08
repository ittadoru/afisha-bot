# ruff: noqa: RUF001 -- Russian event examples are intentional.

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from afishabot.adapters.http.events import CreateEventRequest


def event_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Прогулка",
        "description": "Встречаемся у входа.",
        "category_id": uuid4(),
        "city_id": uuid4(),
        "starts_at": datetime(2026, 8, 10, 15, tzinfo=UTC),
        "ends_at": datetime(2026, 8, 10, 17, tzinfo=UTC),
        "latitude": 42.98,
        "longitude": 47.50,
        "address_visibility": "exact_public",
        "address_text": "  улица  Гагарина,  дом  12 ",
        "address_confirmed": True,
        "photo_upload_id": uuid4(),
    }
    payload.update(overrides)
    return payload


def test_create_event_address_text_is_normalized() -> None:
    request = CreateEventRequest.model_validate(event_payload())

    assert request.address_text == "улица Гагарина, дом 12"
    assert request.address_confirmed is True


@pytest.mark.parametrize("address", ["", " \t ", "улица\nГагарина"])
def test_create_event_rejects_blank_or_control_address_text(address: str) -> None:
    with pytest.raises(ValidationError):
        CreateEventRequest.model_validate(event_payload(address_text=address))
