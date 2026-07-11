from collections.abc import AsyncGenerator

import structlog

logger = structlog.get_logger()


class FailoverLLMService:
    """Wraps multiple LLM service instances and falls over to the next one if a call
    fails — originally for spreading app-default load across separate per-key rate
    limits on the same provider (e.g. two Gemini API keys), extended (Phase 12) to
    also chain across different providers entirely (e.g. Gemini keys, then Groq as a
    last resort) since each provider's free-tier quota is a genuinely separate pool.
    Works either way — every wrapped service shares the same generate/stream_generate/
    health_check interface regardless of provider.

    Streaming only fails over if the failing service hasn't yielded any tokens yet
    (a rate-limit/connection error typically happens before the first chunk). Once
    output has started, a mid-stream failure is re-raised as-is rather than retried,
    since restarting on a second key would send a duplicated/broken response."""

    def __init__(self, services: list) -> None:
        if not services:
            raise ValueError("FailoverLLMService needs at least one underlying service")
        self._services = services

    async def generate(
        self, prompt: str, system_prompt: str = "", json_mode: bool = False
    ) -> str:
        last_exc: Exception | None = None
        for svc in self._services:
            try:
                return await svc.generate(prompt, system_prompt=system_prompt, json_mode=json_mode)
            except Exception as exc:
                last_exc = exc
                logger.warning("llm_failover", error=str(exc))
        raise last_exc  # type: ignore[misc]

    async def stream_generate(
        self, prompt: str, system_prompt: str = ""
    ) -> AsyncGenerator[str, None]:
        last_exc: Exception | None = None
        for svc in self._services:
            started = False
            try:
                async for token in svc.stream_generate(prompt, system_prompt=system_prompt):
                    started = True
                    yield token
                return
            except Exception as exc:
                last_exc = exc
                logger.warning("llm_failover_stream", error=str(exc), started=started)
                if started:
                    raise
        raise last_exc  # type: ignore[misc]

    async def health_check(self) -> bool:
        for svc in self._services:
            if await svc.health_check():
                return True
        return False
