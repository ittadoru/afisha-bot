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
    tg_proxy_url: SecretStr | None = None
    afisha_mini_app_url: HttpUrl | None = None
    afisha_log_level: str = "INFO"

    @field_validator("tg_proxy_url", "afisha_mini_app_url", mode="before")
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

    def proxy_url(self) -> str | None:
        if self.tg_proxy_url is None:
            return None
        value = self.tg_proxy_url.get_secret_value().strip()
        return value or None

    def validated(self) -> Self:
        """Make transport validation explicit at the runtime call site."""
        return self


def load_bot_settings() -> BotSettings:
    return BotSettings()  # pyright: ignore[reportCallIssue]
