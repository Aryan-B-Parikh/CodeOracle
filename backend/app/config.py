"""Application settings, loaded from environment / backend `.env`."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "CodeOracle API"
    database_url: str = "postgresql+psycopg://codeoracle:codeoracle@localhost:5432/codeoracle"
    redis_url: str = "redis://localhost:6379/0"
    upload_dir: Path = Path("./uploads")
    llm_api_key: str = ""
    llm_provider: str = "openai"
    llm_model: str = ""
    embedding_model: str = ""
    sandbox_image: str = "codeoracle/sandbox:latest"
    sandbox_timeout_seconds: int = 300
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
