"""AI-powered article summarization service using Microsoft Foundry (GPT-4.1)."""

import logging
from dataclasses import dataclass

from openai import APIError, RateLimitError

from api.services.llm import chat_completion

logger = logging.getLogger(__name__)

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
    """Parse the LLM response into summary and key takeaways.

    Args:
        response_text: Raw response from the LLM.

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
    # Truncate content if too long
    max_content_length = 10000
    if len(content) > max_content_length:
        content = content[:max_content_length] + "..."

    prompt = SUMMARIZATION_PROMPT.format(title=title, content=content)

    for attempt in range(max_retries + 1):
        try:
            response_text = await chat_completion(
                prompt=prompt,
                max_tokens=500,
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
            raise SummarizationError(
                f"Rate limited after {max_retries + 1} attempts"
            ) from e

        except APIError as e:
            logger.error("LLM API error: %s", e)
            raise SummarizationError(f"API error: {e}") from e

    raise SummarizationError("Unexpected error in retry loop")
