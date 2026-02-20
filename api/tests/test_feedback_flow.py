"""Tests for the feedback endpoint.

Covers rate limiting, honeypot, spam triage, and issue creation.
"""

import time
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient

from api.models.feedback import TriageResult
from api.routers.feedback import RATE_LIMIT_MAX, RATE_LIMIT_WINDOW, _check_rate_limit


def test_rate_limit_allows_under_threshold():
    ip = "10.0.0.1"
    for _ in range(RATE_LIMIT_MAX):
        assert _check_rate_limit(ip) is True
    # Next call should be blocked
    assert _check_rate_limit(ip) is False


def test_rate_limit_resets_after_window(mocker):
    ip = "10.0.0.2"

    # Fill to limit
    for _ in range(RATE_LIMIT_MAX):
        _check_rate_limit(ip)
    assert _check_rate_limit(ip) is False

    # Advance time past the window
    future = time.time() + RATE_LIMIT_WINDOW + 1
    mocker.patch("api.routers.feedback.time.time", return_value=future)

    assert _check_rate_limit(ip) is True


async def test_honeypot_returns_fake_response(mock_settings, mocker):
    # Mock triage to verify it is NOT called
    mock_triage = mocker.patch(
        "api.routers.feedback.triage_feedback",
        new_callable=AsyncMock,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/fishbowl/feedback",
            json={
                "title": "Bot feedback title here",
                "description": (
                    "This is a bot submitting feedback with honeypot field filled"
                ),
                "website": "https://spam.example.com",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["issue_number"] == 0
    mock_triage.assert_not_called()


async def test_spam_triage_returns_fake_response(mock_settings, mocker):
    mocker.patch(
        "api.routers.feedback.triage_feedback",
        new_callable=AsyncMock,
        return_value=TriageResult(
            is_spam=True,
            confidence=0.95,
            feedback_type="other",
            labels=[],
            reasoning="Spam content",
        ),
    )
    mock_create = mocker.patch(
        "api.routers.feedback.create_github_issue",
        new_callable=AsyncMock,
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/fishbowl/feedback",
            json={
                "title": "Buy cheap products now",
                "description": (
                    "Amazing deals available at our website check it out now"
                ),
            },
        )

    assert response.status_code == 200
    assert response.json()["issue_number"] == 0
    mock_create.assert_not_called()


async def test_successful_submission_creates_issue(mock_settings, mocker):
    mocker.patch(
        "api.routers.feedback.triage_feedback",
        new_callable=AsyncMock,
        return_value=TriageResult(
            is_spam=False,
            confidence=0.1,
            feedback_type="enhancement",
            labels=["enhancement"],
            reasoning="Legitimate feature request",
        ),
    )
    mocker.patch(
        "api.routers.feedback.create_github_issue",
        new_callable=AsyncMock,
        return_value={
            "html_url": "https://github.com/testowner/testrepo/issues/42",
            "number": 42,
        },
    )

    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/fishbowl/feedback",
            json={
                "title": "Add dark mode support",
                "description": (
                    "It would be great to have a dark mode toggle in the settings page"
                ),
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["issue_number"] == 42
    assert "github.com" in data["issue_url"]
