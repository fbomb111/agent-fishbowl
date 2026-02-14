"""Application configuration via environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # App
    debug: bool = False
    environment: str = "development"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Azure Blob Storage
    azure_storage_account: str = ""
    azure_storage_container: str = "articles"

    # GitHub (for activity feed)
    github_repo: str = "fbomb111/agent-fishbowl"
    github_token: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
