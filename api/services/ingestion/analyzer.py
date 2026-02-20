"""AI-powered article analysis — extracts actionable insights using Foundry GPT-4.1."""

import json
import logging
from dataclasses import dataclass, field

from openai import APIError, RateLimitError

from api.services.llm import chat_completion

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = (
    "You are an AI technology analyst for a software development "
    "team. Given an article, extract actionable insights — things "
    "a development team could learn or start applying today.\n"
    "\n"
    "Focus on:\n"
    "- New tools, libraries, or frameworks worth evaluating\n"
    "- Design patterns or architectural approaches\n"
    "- Industry trends that affect technical decisions\n"
    "- Practical techniques or best practices\n"
    "- Important concepts or mental models\n"
    "\n"
    "Not every article will have actionable insights. News "
    "announcements, opinion pieces, or general coverage may have "
    "zero insights — that's fine. Only extract insights that are "
    "genuinely useful and actionable.\n"
    "\n"
    "Article Title: {title}\n"
    "\n"
    "Article Content:\n"
    "{content}\n"
    "\n"
    "Respond with valid JSON in this exact format:\n"
    "{{\n"
    '  "insights": [\n'
    '    {{"text": "Concise, actionable insight description", '
    '"category": "tool|pattern|trend|technique|concept"}}\n'
    "  ],\n"
    '  "ai_summary": "A 2-3 sentence summary of the article\'s '
    "key points. Only include if the content is substantial "
    'enough to warrant a summary beyond the RSS description.",\n'
    '  "relevance_score": 7\n'
    "}}\n"
    "\n"
    "Rules:\n"
    "- insights: 0-5 items. Empty list is perfectly fine for "
    "non-actionable content.\n"
    "- category must be one of: tool, pattern, trend, technique, "
    "concept\n"
    "- ai_summary: null if the content is too short or is just "
    "an RSS snippet\n"
    "- Each insight should be self-contained and understandable "
    "without reading the article\n"
    "- relevance_score: integer 1-10 rating of how relevant and "
    "valuable this article is for AI/ML practitioners. Score "
    "based on: practical value (can readers apply this?), "
    "technical depth (beyond surface-level coverage?), and "
    "novelty (new information vs rehashed content?). Generic "
    "announcements, opinion pieces, and corporate press releases "
    "score low (1-4). In-depth technical content, novel research, "
    "and practical tutorials score high (7-10)."
)


@dataclass
class AnalysisResult:
    """Result of article analysis."""

    insights: list[dict[str, str]] = field(default_factory=list)
    ai_summary: str | None = None
    relevance_score: int = 5


MAX_CONTENT_LENGTH = 12000


class AnalysisError(Exception):
    """Error during article analysis."""

    pass


def _parse_response(response_text: str) -> AnalysisResult:
    """Parse the JSON response from the LLM."""
    try:
        data = json.loads(response_text)

        insights = []
        for item in data.get("insights", []):
            if isinstance(item, dict) and "text" in item:
                insights.append(
                    {
                        "text": item["text"],
                        "category": item.get("category", "concept"),
                    }
                )

        ai_summary = data.get("ai_summary")
        if ai_summary and len(ai_summary.strip()) < 20:
            ai_summary = None

        relevance_score = data.get("relevance_score", 5)
        if not isinstance(relevance_score, int):
            relevance_score = 5
        relevance_score = max(1, min(10, relevance_score))

        return AnalysisResult(
            insights=insights, ai_summary=ai_summary, relevance_score=relevance_score
        )

    except json.JSONDecodeError as e:
        raise AnalysisError(f"Invalid JSON response: {e}") from e
    except Exception as e:
        raise AnalysisError(f"Failed to parse response: {e}") from e


async def analyze_article(
    title: str,
    content: str,
    max_retries: int = 2,
) -> AnalysisResult:
    """Analyze an article and extract actionable insights.

    Args:
        title: Article title.
        content: Full article text or RSS description.
        max_retries: Maximum retry attempts on rate limiting.

    Returns:
        Analysis result with insights and optional summary.

    Raises:
        AnalysisError: If analysis fails after retries.
    """
    if len(content) > MAX_CONTENT_LENGTH:
        content = content[:MAX_CONTENT_LENGTH] + "..."

    prompt = ANALYSIS_PROMPT.format(title=title, content=content)

    for attempt in range(max_retries + 1):
        try:
            response_text = await chat_completion(
                prompt=prompt,
                max_tokens=800,
                temperature=0.3,
            )
            return _parse_response(response_text)

        except RateLimitError as e:
            if attempt < max_retries:
                logger.warning(
                    "Rate limited, attempt %d/%d: %s",
                    attempt + 1,
                    max_retries + 1,
                    e,
                )
                continue
            raise AnalysisError(f"Rate limited after {max_retries + 1} attempts") from e

        except APIError as e:
            logger.error("LLM API error: %s", e)
            raise AnalysisError(f"API error: {e}") from e
