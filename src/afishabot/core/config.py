from enum import StrEnum
from pathlib import Path

from pydantic import Field, SecretStr
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

    def database_dsn(self) -> str:
        return self.database_url.get_secret_value()

    def redis_dsn(self) -> str:
        return self.redis_url.get_secret_value()
