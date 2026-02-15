"""Feedback submission models."""

from pydantic import BaseModel, Field


class FeedbackSubmission(BaseModel):
    """User feedback form submission."""

    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=20, max_length=5000)
    email: str | None = Field(None, max_length=200)
    website: str = ""  # Honeypot — bots fill this, humans don't


class TriageResult(BaseModel):
    """AI triage analysis result."""

    is_spam: bool
    confidence: float = 0.5
    feedback_type: str  # bug, enhancement, question, feedback, other
    labels: list[str] = []
    reasoning: str = ""


class FeedbackResponse(BaseModel):
    """Response after feedback submission."""

    issue_url: str
    issue_number: int
    message: str
