import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import pytest

from afishabot.modules.accounts.domain.telegram_auth import (
    TelegramAuthError,
    verify_telegram_init_data,
)

BOT_TOKEN = "123456:test-token"
NOW = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


def signed_init_data(
    *,
    user_id: int = 42,
    auth_date: datetime = NOW,
) -> str:
    values = {
        "auth_date": str(int(auth_date.timestamp())),
        "query_id": "query-1",
        "user": json.dumps({"id": user_id, "username": "must-not-be-used"}),
    }
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(
        secret,
        check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(values)


def test_valid_init_data_returns_only_verified_identity() -> None:
    verified = verify_telegram_init_data(signed_init_data(), BOT_TOKEN, now=NOW)

    assert verified.telegram_user_id == 42
    assert verified.auth_date == NOW
    assert len(verified.payload_digest) == 64


def test_forged_init_data_is_rejected() -> None:
    forged = signed_init_data().replace("query-1", "query-2")

    with pytest.raises(TelegramAuthError, match="signature"):
        verify_telegram_init_data(forged, BOT_TOKEN, now=NOW)


@pytest.mark.parametrize(
    "auth_date, message",
    [
        (NOW - timedelta(minutes=5, seconds=1), "expired"),
        (NOW + timedelta(seconds=31), "future"),
    ],
)
def test_init_data_time_window_is_enforced(
    auth_date: datetime,
    message: str,
) -> None:
    with pytest.raises(TelegramAuthError, match=message):
        verify_telegram_init_data(
            signed_init_data(auth_date=auth_date),
            BOT_TOKEN,
            now=NOW,
        )


def test_duplicate_fields_are_rejected() -> None:
    raw = signed_init_data()

    with pytest.raises(TelegramAuthError, match="duplicate"):
        verify_telegram_init_data(f"{raw}&auth_date=1", BOT_TOKEN, now=NOW)
