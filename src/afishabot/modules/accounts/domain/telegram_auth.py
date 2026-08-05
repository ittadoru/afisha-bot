import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl


class TelegramAuthError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class VerifiedTelegramUser:
    telegram_user_id: int
    auth_date: datetime
    payload_digest: str


def verify_telegram_init_data(
    raw_init_data: str,
    bot_token: str,
    *,
    now: datetime | None = None,
) -> VerifiedTelegramUser:
    if not raw_init_data or len(raw_init_data.encode()) > 8192:
        raise TelegramAuthError("invalid initData size")

    try:
        pairs = parse_qsl(
            raw_init_data,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=64,
        )
    except ValueError as error:
        raise TelegramAuthError("invalid initData shape") from error

    values: dict[str, str] = {}
    for key, value in pairs:
        if key in values:
            raise TelegramAuthError("duplicate initData field")
        values[key] = value

    supplied_hash = values.pop("hash", None)
    if supplied_hash is None or len(supplied_hash) != 64:
        raise TelegramAuthError("missing initData hash")
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(values.items())
    )
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, supplied_hash.lower()):
        raise TelegramAuthError("invalid initData signature")

    try:
        auth_date = datetime.fromtimestamp(int(values["auth_date"]), tz=UTC)
        user = json.loads(values["user"])
        telegram_user_id = int(user["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, OverflowError) as error:
        raise TelegramAuthError("invalid Telegram user") from error
    if telegram_user_id <= 0:
        raise TelegramAuthError("invalid Telegram user")

    current_time = now or datetime.now(UTC)
    if auth_date > current_time + timedelta(seconds=30):
        raise TelegramAuthError("future initData")
    if auth_date < current_time - timedelta(minutes=5):
        raise TelegramAuthError("expired initData")

    return VerifiedTelegramUser(
        telegram_user_id=telegram_user_id,
        auth_date=auth_date,
        payload_digest=hashlib.sha256(raw_init_data.encode()).hexdigest(),
    )
