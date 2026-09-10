"""Settings Module."""

import uuid
from enum import Enum

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Labels:
    """Labels Model."""

    NAMESPACE_LABEL_KEY = "h8ber-mate/enabled"
    NAMESPACE_LABEL_VALUE = "true"


class Environment(str, Enum):
    """ENUM Environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """ENUM LogLevel."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Auth(BaseSettings):
    """Authentication settings."""

    ADMIN_EMAIL: str = "admin@h8ber-mate.local"
    ADMIN_PASSWORD: str = "admin"
    JWT_SECRET_KEY: str = str(uuid.uuid4())
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # Refresh tokens expire after 7 days


class SnoozeOptions(BaseSettings):
    """Snooze options settings."""

    FLUXCD_OPTION: bool = False
    ARGOCD_OPTION: bool = False


class DatabaseType(str, Enum):
    """ENUM Database Types."""

    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


class Database(BaseSettings):
    """Database settings."""

    DB_TYPE: DatabaseType = DatabaseType.SQLITE  # Default to SQLite for easier setup
    SQLITE_PATH: str = "./data/h8ber-mate.db"  # Path for SQLite database file

    # PostgreSQL settings (only needed if DB_TYPE=postgresql)
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 5432
    DB_USER: str = "h8ber-mate"
    DB_PASSWORD: str = "mysecretpassword"
    DB_DB: str = "h8ber-mate"

    @property
    def DB_URI(self) -> str:  # noqa: N802
        """Construct the database URI based on DB_TYPE."""
        if self.DB_TYPE == DatabaseType.SQLITE:
            return f"sqlite+aiosqlite:///{self.SQLITE_PATH}"
        else:
            # PostgreSQL connection
            return PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.DB_USER,
                password=self.DB_PASSWORD,
                host=self.DB_HOST,
                port=int(self.DB_PORT),
                path=self.DB_DB,
            ).unicode_string()

    @field_validator("DB_USER", "DB_PASSWORD", mode="before")
    @classmethod
    def check_if_at(cls, field_value) -> str:
        if "@" in field_value:
            raise ValueError("Character '@' is not allowed in database USER or PASSWORD fields.")
        return field_value


class Settings(Database, Auth, SnoozeOptions, BaseSettings):
    """API settings."""

    # ENV
    PORT: int = 8000
    ENVIRONMENT: Environment = Environment.PRODUCTION
    LOG_LEVEL: LogLevel = LogLevel.INFO
    DEBUG: bool = False
    TIMEZONE: str = "Europe/Paris"

    labels: Labels = Labels()

    model_config = SettingsConfigDict(
        # .env.prod takes priority over `.env`
        env_file=(".env", ".env.prod"),
        extra="ignore",
    )


settings = Settings()
