import json
import logging

from afishabot.core.logging import JsonFormatter, configure_logging


def test_json_logging_uses_an_allowlist() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="safe message",
        args=(),
        exc_info=None,
    )
    record.password = "must-not-leak"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "safe message"
    assert "password" not in payload


def test_json_logging_includes_safe_event_diagnostics() -> None:
    request_id = "11111111-1111-4111-8111-111111111111"
    city_id = "10000000-0000-4000-8000-000000000001"
    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="event_creation_rejected",
        args=(),
        exc_info=None,
    )
    record.request_id = request_id
    record.stage = "create_event"
    record.reason = "organizer_not_eligible"
    record.city_id = city_id
    record.address = "must-not-leak"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "event_creation_rejected"
    assert payload["request_id"] == request_id
    assert payload["stage"] == "create_event"
    assert payload["reason"] == "organizer_not_eligible"
    assert payload["city_id"] == city_id
    assert "address" not in payload


def test_logging_configuration_uses_json_handler() -> None:
    configure_logging("WARNING")

    root = logging.getLogger()
    assert root.level == logging.WARNING
    assert isinstance(root.handlers[0].formatter, JsonFormatter)
