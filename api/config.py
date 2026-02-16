"""Application configuration via environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # App
    debug: bool = False
    environment: str = "development"

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3010",
        "http://localhost:8080",
        "http://localhost:8500",
        "https://polite-tree-06036620f.1.azurestaticapps.net",
        "https://agentfishbowl.com",
    ]

    # Azure Blob Storage
    azure_storage_account: str = ""
    azure_storage_container: str = "articles"

    # Azure User-Assigned Managed Identity — used in ALL environments
    managed_identity_client_id: str = ""

    # GitHub (for activity feed)
    github_repo: str = ""
    github_token: str = ""

    # Microsoft Foundry (LLM access via OpenAI-compatible API)
    foundry_openai_endpoint: str = ""  # https://fishbowl.openai.azure.com/openai/v1/
    foundry_api_key: str = ""
    foundry_deployment: str = "gpt-4.1"

    # Ingestion API key (protects POST /api/ingest)
    ingest_api_key: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
