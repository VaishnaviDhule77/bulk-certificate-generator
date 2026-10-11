"""Application configuration loaded from environment variables or a .env file."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings, overridable via environment or .env."""

    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/certificate_db"
    )
    output_dir: Path = Path("storage/certificates")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()