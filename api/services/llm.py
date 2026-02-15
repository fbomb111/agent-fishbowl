"""Microsoft Foundry LLM client via OpenAI-compatible API.

Usage:
    from api.services.llm import chat_completion

    response = await chat_completion("Summarize this article: ...")
"""

import logging

from openai import AsyncOpenAI

from api.config import get_settings

logger = logging.getLogger(__name__)


def _get_client() -> AsyncOpenAI:
    """Create an async OpenAI client pointed at the Foundry endpoint."""
    settings = get_settings()
    return AsyncOpenAI(
        base_url=settings.foundry_openai_endpoint,
        api_key=settings.foundry_api_key,
    )


async def chat_completion(
    prompt: str,
    model: str | None = None,
    max_tokens: int = 1000,
    temperature: float = 0.7,
) -> str:
    """Run a chat completion against the Foundry-deployed model.

    Args:
        prompt: The user message to send.
        model: Override the default deployment name.
        max_tokens: Maximum response tokens.
        temperature: Sampling temperature.

    Returns:
        The assistant's response text.

    Raises:
        openai.APIError: On API errors.
    """
    settings = get_settings()
    client = _get_client()

    response = await client.chat.completions.create(
        model=model or settings.foundry_deployment,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )

    return response.choices[0].message.content or ""
