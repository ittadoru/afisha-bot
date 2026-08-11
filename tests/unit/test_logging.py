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


def test_logging_configuration_uses_json_handler() -> None:
    configure_logging("WARNING")

    root = logging.getLogger()
    assert root.level == logging.WARNING
    assert isinstance(root.handlers[0].formatter, JsonFormatter)
