"""AI-powered article summarization service using Claude."""

import logging
from dataclasses import dataclass

from anthropic import APIError, AsyncAnthropic, RateLimitError

from api.config import get_settings

logger = logging.getLogger(__name__)

# Use claude-3-haiku for cost efficiency on high volume
MODEL = "claude-3-haiku-20240307"

# Prompt for generating summaries
SUMMARIZATION_PROMPT = """You are a news summarizer. Given an article title and content, generate:
1. A concise 2-3 sentence summary that captures the key information
2. 3-5 key takeaways as bullet points

Be factual and neutral. Do not editorialize or add opinions.

Article Title: {title}

Article Content:
{content}

Respond in this exact format:
SUMMARY:
[Your 2-3 sentence summary here]

KEY TAKEAWAYS:
- [First takeaway]
- [Second takeaway]
- [Third takeaway]
- [Optional fourth takeaway]
- [Optional fifth takeaway]"""


@dataclass
class SummarizationResult:
    """Result of article summarization."""

    summary: str
    key_takeaways: list[str]


class SummarizationError(Exception):
    """Error during article summarization."""

    pass


def _parse_response(response_text: str) -> SummarizationResult:
    """Parse the Claude response into summary and key takeaways.

    Args:
        response_text: Raw response from Claude API.

    Returns:
        Parsed summarization result.

    Raises:
        SummarizationError: If response cannot be parsed.
    """
    try:
        # Split by KEY TAKEAWAYS
        parts = response_text.split("KEY TAKEAWAYS:")
        if len(parts) != 2:
            raise SummarizationError("Response missing KEY TAKEAWAYS section")

        # Extract summary (remove "SUMMARY:" prefix)
        summary_part = parts[0].strip()
        if summary_part.startswith("SUMMARY:"):
            summary_part = summary_part[8:].strip()
        summary = summary_part.strip()

        # Extract key takeaways
        takeaways_text = parts[1].strip()
        key_takeaways: list[str] = []
        for line in takeaways_text.split("\n"):
            line = line.strip()
            if line.startswith("- "):
                takeaway = line[2:].strip()
                if takeaway:
                    key_takeaways.append(takeaway)

        if not summary:
            raise SummarizationError("Empty summary in response")

        if len(key_takeaways) < 3:
            raise SummarizationError(
                f"Expected at least 3 takeaways, got {len(key_takeaways)}"
            )

        return SummarizationResult(summary=summary, key_takeaways=key_takeaways)

    except SummarizationError:
        raise
    except Exception as e:
        raise SummarizationError(f"Failed to parse response: {e}") from e


async def summarize_article(
    title: str,
    content: str,
    max_retries: int = 2,
) -> SummarizationResult:
    """Generate an AI summary and key takeaways for an article.

    Args:
        title: Article title.
        content: Article content or description.
        max_retries: Maximum retry attempts on rate limiting.

    Returns:
        Summarization result with summary and key takeaways.

    Raises:
        SummarizationError: If summarization fails after retries.
    """
    settings = get_settings()

    if not settings.anthropic_api_key:
        raise SummarizationError("ANTHROPIC_API_KEY not configured")

    # Truncate content if too long (Claude has context limits)
    max_content_length = 10000
    if len(content) > max_content_length:
        content = content[:max_content_length] + "..."

    prompt = SUMMARIZATION_PROMPT.format(title=title, content=content)

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    for attempt in range(max_retries + 1):
        try:
            message = await client.messages.create(
                model=MODEL,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text
            return _parse_response(response_text)

        except RateLimitError as e:
            if attempt < max_retries:
                logger.warning(
                    "Rate limited, attempt %d/%d: %s",
                    attempt + 1,
                    max_retries + 1,
                    e,
                )
                # Let the caller handle backoff if needed
                continue
            raise SummarizationError(f"Rate limited after {max_retries + 1} attempts")

        except APIError as e:
            logger.error("Anthropic API error: %s", e)
            raise SummarizationError(f"API error: {e}") from e

    # Should not reach here, but satisfy type checker
    raise SummarizationError("Unexpected error in retry loop")
