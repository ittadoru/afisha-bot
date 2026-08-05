from enum import StrEnum
from pathlib import Path

from pydantic import Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Validated process configuration. Instances are created at app startup."""

    model_config = SettingsConfigDict(
        env_prefix="AFISHA_",
        extra="forbid",
        case_sensitive=False,
    )

    environment: Environment = Environment.STAGING
    debug: bool = False
    log_level: str = "INFO"
    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://afisha:change-me@postgres:5432/afisha"
    )
    redis_url: SecretStr = SecretStr("redis://redis:6379/0")
    media_root: Path = Path("/var/lib/afisha/media")
    readiness_timeout_seconds: float = Field(default=2.0, gt=0, le=10)
    nominatim_url: str = "http://nominatim:8080"
    nominatim_timeout_seconds: float = Field(default=1.2, gt=0, le=2.5)
    public_base_url: HttpUrl = HttpUrl("https://podvval.xyz")
    admin_base_url: HttpUrl = HttpUrl("https://admin.podvval.xyz")
    telegram_bot_token: SecretStr | None = Field(
        default=None,
        validation_alias="BOT_TOKEN",
    )
    auth_hmac_secret: SecretStr | None = Field(default=None, min_length=32)
    admin_login: str | None = Field(
        default=None,
        max_length=64,
        validation_alias="ADMIN_LOGIN",
    )
    admin_password: SecretStr | None = Field(
        default=None,
        max_length=256,
        validation_alias="ADMIN_PASSWORD",
    )

    @field_validator("public_base_url", "admin_base_url")
    @classmethod
    def public_urls_must_use_https(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("public URLs must use HTTPS")
        return value

    def database_dsn(self) -> str:
        return self.database_url.get_secret_value()

    def redis_dsn(self) -> str:
        return self.redis_url.get_secret_value()

    def bot_token(self) -> str | None:
        if self.telegram_bot_token is None:
            return None
        return self.telegram_bot_token.get_secret_value()

    def auth_secret(self) -> bytes | None:
        if self.auth_hmac_secret is None:
            return None
        return self.auth_hmac_secret.get_secret_value().encode()

    def bootstrap_admin_password(self) -> str | None:
        if self.admin_password is None:
            return None
        return self.admin_password.get_secret_value()
