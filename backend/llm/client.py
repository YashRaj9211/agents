"""One tiny OpenAI-compatible LLM client."""
from __future__ import annotations

from typing import Any

# pyrefly: ignore [missing-import]
from openai import AsyncOpenAI

from config import settings


class LlmClient:
    def __init__(self) -> None:
        if not settings.llm_api_key or not settings.llm_model:
            raise RuntimeError("Set LLM_API_KEY and LLM_MODEL in backend/.env before running.")
        self._client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )

    async def decide(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]):
        response = await self._client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0,
        )
        return response.choices[0].message
