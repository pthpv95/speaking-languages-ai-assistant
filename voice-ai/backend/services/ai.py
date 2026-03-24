from __future__ import annotations

import io
from collections.abc import AsyncIterator

from openai import AsyncOpenAI, OpenAI

from backend.core.config import Settings


class AIService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.async_client = AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=settings.groq_api_key)
        self.sync_client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=settings.groq_api_key)

    async def transcribe(self, *, audio_bytes: bytes, filename: str, content_type: str, model: str, language: str) -> str:
        result = await self.async_client.audio.transcriptions.create(
            model=model,
            file=(filename, io.BytesIO(audio_bytes), content_type),
            language=language,
            response_format="json",
            temperature=0.0,
        )
        return result.text.strip()

    async def complete_chat(self, *, messages: list[dict], max_tokens: int = 200, temperature: float = 0.7) -> str:
        response = await self.async_client.chat.completions.create(
            model=self.settings.chat_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()

    async def stream_chat(
        self, *, messages: list[dict], max_tokens: int = 200, temperature: float = 0.7
    ) -> AsyncIterator[str]:
        stream = await self.async_client.chat.completions.create(
            model=self.settings.chat_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def summarize(self, context: str) -> str:
        response = await self.async_client.chat.completions.create(
            model=self.settings.summary_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Summarize the conversation below in 2-4 concise sentences. "
                        "Capture: user's name/level, topics discussed, key corrections made, "
                        "and where the conversation left off. Write in third person. "
                        "Keep it under 100 words."
                    ),
                },
                {"role": "user", "content": context},
            ],
            max_tokens=self.settings.summary_max_tokens,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
