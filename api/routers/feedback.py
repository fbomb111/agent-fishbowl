"""Feedback submission endpoint with rate limiting and spam protection."""

import logging
import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request

from api.models.feedback import FeedbackResponse, FeedbackSubmission
from api.services.feedback import create_github_issue, triage_feedback

router = APIRouter(prefix="/feedback", tags=["feedback"])
logger = logging.getLogger(__name__)

# In-memory rate limiter: {ip: [timestamps]}
_rate_limits: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 3600  # 1 hour
RATE_LIMIT_MAX = 5

# Fake response for spam/honeypot (identical to real success)
_FAKE_RESPONSE = FeedbackResponse(
    issue_url="",
    issue_number=0,
    message="Thank you for your feedback!",
)


def _check_rate_limit(ip: str) -> bool:
    """Return True if request is allowed, False if rate limited."""
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW
    _rate_limits[ip] = [ts for ts in _rate_limits[ip] if ts > cutoff]
    if len(_rate_limits[ip]) >= RATE_LIMIT_MAX:
        return False
    _rate_limits[ip].append(now)
    return True


@router.post("", response_model=FeedbackResponse)
async def submit_feedback(submission: FeedbackSubmission, request: Request):
    """Submit feedback. AI-triaged and created as a GitHub issue."""
    client_ip = request.client.host if request.client else "unknown"

    # Rate limit
    if not _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429, detail="Too many submissions. Try again later."
        )

    # Honeypot (silent discard)
    if submission.website:
        logger.warning("Honeypot triggered from %s", client_ip)
        return _FAKE_RESPONSE

    # AI triage
    triage = await triage_feedback(submission)

    # Spam check (silent discard)
    if triage.is_spam and triage.confidence > 0.7:
        logger.warning("Spam detected from %s: %s", client_ip, submission.title[:50])
        return _FAKE_RESPONSE

    # Create GitHub issue
    try:
        issue = await create_github_issue(submission, triage)
    except Exception as e:
        logger.error("GitHub issue creation failed: %s", e)
        raise HTTPException(
            status_code=500, detail="Failed to create issue. Please try again."
        )

    logger.info(
        "Created issue #%d from %s: %s",
        issue["number"],
        client_ip,
        submission.title[:50],
    )

    return FeedbackResponse(
        issue_url=issue["html_url"],
        issue_number=issue["number"],
        message=f"Your feedback has been created as issue #{issue['number']}. You can track it at the link above.",
    )
