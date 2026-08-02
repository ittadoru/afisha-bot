from typing import Self

from pydantic import HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    """Validated Telegram settings loaded from the process environment."""

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
        case_sensitive=False,
    )

    bot_token: SecretStr
    tg_proxy_url: SecretStr
    afisha_mini_app_url: HttpUrl | None = None
    afisha_log_level: str = "INFO"

    @field_validator("afisha_mini_app_url", mode="before")
    @classmethod
    def empty_url_is_unset(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator("afisha_mini_app_url")
    @classmethod
    def mini_app_must_use_https(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is not None and value.scheme != "https":
            raise ValueError("AFISHA_MINI_APP_URL must use HTTPS")
        return value

    def token(self) -> str:
        return self.bot_token.get_secret_value()

    def proxy_url(self) -> str:
        return self.tg_proxy_url.get_secret_value()

    def validated(self) -> Self:
        """Make the required transport policy explicit at the call site."""
        if not self.proxy_url().strip():
            raise ValueError("TG_PROXY_URL must not be empty")
        return self


def load_bot_settings() -> BotSettings:
    return BotSettings()  # pyright: ignore[reportCallIssue]
