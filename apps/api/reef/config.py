from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: str = "production"
    database_url: str = "postgresql+psycopg://reef:reef@127.0.0.1:5432/reef"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    session_hours: int = 8
    dev_auth_bypass: bool = False
    db_pool_size: int = 5

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value):
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @model_validator(mode="after")
    def safe_auth(self):
        if self.dev_auth_bypass and self.environment not in {"development", "test"}:
            raise ValueError("DEV_AUTH_BYPASS is forbidden outside development/test")
        if self.environment == "production" and any(
            not x.startswith("https://") for x in self.cors_origins.split(",")
        ):
            raise ValueError("Production CORS origins must use HTTPS")
        return self


@lru_cache
def settings() -> Settings:
    return Settings()
