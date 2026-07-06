import time
from collections.abc import AsyncGenerator

import structlog
from groq import AsyncGroq
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

logger = structlog.get_logger()


class GroqLLMService:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._client = AsyncGroq(api_key=api_key or settings.groq_api_key)
        self._model = model or settings.groq_model

    def _build_messages(self, prompt: str, system_prompt: str) -> list[dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def generate(
        self, prompt: str, system_prompt: str = "", json_mode: bool = False
    ) -> str:
        messages = self._build_messages(prompt, system_prompt)
        kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
        start = time.monotonic()
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            **kwargs,
        )
        latency_ms = round((time.monotonic() - start) * 1000)
        usage = response.usage
        logger.info(
            "llm_call",
            provider="groq",
            model=self._model,
            streamed=False,
            latency_ms=latency_ms,
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
        )
        return response.choices[0].message.content

    async def stream_generate(
        self, prompt: str, system_prompt: str = ""
    ) -> AsyncGenerator[str, None]:
        messages = self._build_messages(prompt, system_prompt)
        start = time.monotonic()
        chunk_count = 0
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                chunk_count += 1
                yield content
        logger.info(
            "llm_call",
            provider="groq",
            model=self._model,
            streamed=True,
            latency_ms=round((time.monotonic() - start) * 1000),
            chunk_count=chunk_count,
        )

    async def health_check(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False
