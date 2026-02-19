"""Shared fixtures for agent-fishbowl tests."""

import pytest

from api.services.cache import TTLCache


@pytest.fixture(autouse=True)
def _reset_global_state():
    """Reset all module-level singletons and caches between tests."""
    yield

    # 1. Settings LRU cache
    from api.config import get_settings

    get_settings.cache_clear()

    # 2. Blob storage singleton
    import api.services.blob_storage as blob_mod

    blob_mod._container_client = None

    # 3. HTTP client singleton
    import api.services.http_client as http_mod

    http_mod._client = None

    # 4. Goals file cache
    import api.services.goals as goals_mod

    goals_mod._goals_file_cache = None
    goals_mod._goals_file_mtime = 0.0
    goals_mod._cache = TTLCache(ttl=300, max_size=10)

    # 5. Rate limiter state
    import api.routers.feedback as fb_mod

    fb_mod._rate_limits.clear()
    fb_mod._rate_limit_call_count = 0

    # 6. GitHub activity cache
    import api.services.github_activity as gh_activity_mod

    gh_activity_mod._cache = TTLCache(ttl=300, max_size=20)

    # 7. GitHub status cache
    import api.services.github_status as gh_status_mod

    gh_status_mod._status_cache = TTLCache(ttl=60, max_size=5)


@pytest.fixture
def mock_settings(monkeypatch):
    """Provide a Settings object with safe test defaults."""
    from api.config import Settings, get_settings

    test_settings = Settings(
        azure_storage_account="teststorage",
        azure_storage_container="test-articles",
        managed_identity_client_id="test-client-id",
        github_repo="testowner/testrepo",
        github_token="test-token",
        foundry_openai_endpoint="https://test.openai.azure.com/openai/v1/",
        foundry_api_key="test-key",
        foundry_deployment="gpt-4.1",
        ingest_api_key="test-ingest-key",
    )

    get_settings.cache_clear()
    monkeypatch.setattr("api.config.get_settings", lambda: test_settings)

    return test_settings
