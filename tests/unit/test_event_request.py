# ruff: noqa: RUF001

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from afishabot.adapters.http.events import (
    CreateEventRequest,
    _event_creation_http_error,  # pyright: ignore[reportPrivateUsage]
)
from afishabot.adapters.http.middleware import REQUEST_ID
from afishabot.core.logging import JsonFormatter


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
        "address_street": "  улица  Гагарина  ",
        "address_place": "  дом  12 ",
        "address_confirmed": True,
        "photo_upload_id": uuid4(),
    }
    payload.update(overrides)
    return payload


def test_create_event_address_parts_are_normalized() -> None:
    request = CreateEventRequest.model_validate(event_payload())

    assert request.address_street == "улица Гагарина"
    assert request.address_place == "дом 12"
    assert request.address_confirmed is True


@pytest.mark.parametrize("address", ["", " \t ", "улица\nГагарина"])
def test_create_event_rejects_blank_or_control_address_part(address: str) -> None:
    with pytest.raises(ValidationError):
        CreateEventRequest.model_validate(event_payload(address_street=address))


def test_create_event_requires_both_manual_address_parts() -> None:
    with pytest.raises(ValidationError):
        CreateEventRequest.model_validate(event_payload(address_place=""))


def test_create_event_rejects_legacy_combined_address_field() -> None:
    with pytest.raises(ValidationError):
        CreateEventRequest.model_validate(
            event_payload(address_text="улица Гагарина, дом 12")
        )


def test_event_creation_rejection_logs_only_safe_diagnostics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    request_id = "11111111-1111-4111-8111-111111111111"
    city_id = uuid4()
    token = REQUEST_ID.set(request_id)
    try:
        with caplog.at_level("WARNING", logger="afishabot.adapters.http.events"):
            error = _event_creation_http_error(
                stage="create_event",
                reason="organizer_not_eligible",
                city_id=city_id,
            )
    finally:
        REQUEST_ID.reset(token)

    assert error.status_code == 422
    assert error.detail == "organizer_not_eligible"
    assert len(caplog.records) == 1
    record = caplog.records[0]
    payload = json.loads(JsonFormatter().format(record))
    assert payload == {
        "timestamp": payload["timestamp"],
        "level": "WARNING",
        "logger": "afishabot.adapters.http.events",
        "message": "event_creation_rejected",
        "request_id": request_id,
        "stage": "create_event",
        "reason": "organizer_not_eligible",
        "city_id": str(city_id),
    }
