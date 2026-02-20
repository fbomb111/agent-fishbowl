"""Feedback triage and GitHub issue creation service."""

import json
import logging
from typing import Any

from api.config import get_settings
from api.models.feedback import FeedbackSubmission, TriageResult
from api.services.http_client import get_shared_client, github_headers
from api.services.llm import chat_completion

logger = logging.getLogger(__name__)

TRIAGE_PROMPT = """Analyze this user feedback submission for an AI-curated \
news feed project (Agent Fishbowl). Determine:

1. Is this spam, low-quality, or abusive?
2. What type of feedback is it?
3. What GitHub labels should be applied?

SUBMISSION:
Title: {title}
Description: {description}

Respond with valid JSON:
{{
  "is_spam": true/false,
  "confidence": 0.0-1.0,
  "feedback_type": "bug"|"enhancement"|"question"|"feedback"|"other",
  "labels": ["label1", "label2"],
  "reasoning": "Brief explanation"
}}

SPAM CRITERIA:
- Gibberish or nonsensical text
- Commercial/promotional content
- Obvious bot patterns (keyword stuffing, random URLs)
- Abusive or inappropriate language

LABEL GUIDELINES (use existing project labels):
- Type: bug, enhancement, question, documentation
- Optional: good first issue, needs-discussion
- Do NOT add source/* or priority/* labels (other agents handle those)

If unsure whether something is spam, lean toward NOT spam."""


async def triage_feedback(submission: FeedbackSubmission) -> TriageResult:
    """Use AI to classify and validate user feedback."""
    prompt = TRIAGE_PROMPT.format(
        title=submission.title,
        description=submission.description,
    )

    try:
        response = await chat_completion(
            prompt=prompt,
            max_tokens=300,
            temperature=0.3,
        )
        data = json.loads(response)
        return TriageResult(**data)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Failed to parse triage result: %s", e)
        return TriageResult(
            is_spam=False,
            confidence=0.5,
            feedback_type="other",
            labels=["needs-review"],
            reasoning="AI triage parse failed, defaulting to safe values",
        )
    except Exception as e:
        logger.error("Triage failed: %s", e)
        return TriageResult(
            is_spam=False,
            confidence=0.5,
            feedback_type="other",
            labels=["needs-review"],
            reasoning=f"AI triage error: {e}",
        )


async def create_github_issue(
    submission: FeedbackSubmission, triage: TriageResult
) -> dict[str, Any]:
    """Create a GitHub issue from triaged feedback.

    Returns GitHub API response dict with html_url and number.
    """
    settings = get_settings()

    # Build issue body
    body_parts = [
        submission.description,
        "",
        "---",
        "",
        "<details>",
        "<summary>AI Triage</summary>",
        "",
        f"**Type:** {triage.feedback_type}",
        f"**Confidence:** {triage.confidence:.0%}",
        f"**Reasoning:** {triage.reasoning}",
        "",
        "</details>",
    ]

    if submission.email:
        body_parts.extend(["", f"**Contact:** {submission.email}"])

    body = "\n".join(body_parts)

    # Filter to labels that exist (avoid GitHub 422 on unknown labels)
    labels = [label for label in triage.labels if label]

    client = get_shared_client()
    resp = await client.post(
        f"https://api.github.com/repos/{settings.github_repo}/issues",
        headers=github_headers(),
        json={
            "title": submission.title,
            "body": body,
            "labels": labels,
        },
    )
    resp.raise_for_status()
    return resp.json()
