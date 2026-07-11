from collections.abc import AsyncGenerator

import ollama
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings


class LLMService:
    def __init__(self) -> None:
        self._client = ollama.AsyncClient(host=settings.ollama_host)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def generate(
        self, prompt: str, system_prompt: str = "", json_mode: bool = False
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        kwargs = {"format": "json"} if json_mode else {}
        response = await self._client.chat(
            model=settings.ollama_model, messages=messages, **kwargs
        )
        return response.message.content

    async def stream_generate(
        self, prompt: str, system_prompt: str = ""
    ) -> AsyncGenerator[str, None]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        async for chunk in await self._client.chat(
            model=settings.ollama_model, messages=messages, stream=True
        ):
            if chunk.message.content:
                yield chunk.message.content

    async def health_check(self) -> bool:
        try:
            await self._client.list()
            return True
        except Exception:
            return False


# BYOK — known providers with a fixed OpenAI-compatible base_url. Anything else
# requires the user to supply their own base_url when storing the key.
_KNOWN_BYOK_BASE_URLS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "openai": "https://api.openai.com/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "cerebras": "https://api.cerebras.ai/v1",
}
_DEFAULT_BYOK_MODELS = {
    "groq": "openai/gpt-oss-120b",
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4o-mini",
}


def _make_llm_service():
    if settings.llm_provider == "groq":
        from services.groq_llm_service import GroqLLMService
        return GroqLLMService()
    if settings.llm_provider == "gemini":
        from services.openai_compat_llm_service import OpenAICompatLLMService
        from services.failover_llm_service import FailoverLLMService
        from services.groq_llm_service import GroqLLMService

        gemini_keys = [k for k in (settings.gemini_api_key, settings.gemini_api_key_2) if k]
        if not gemini_keys:
            raise ValueError("llm_provider=gemini requires GEMINI_API_KEY to be set")

        # Free-tier failover chain, in priority order. Each provider's free-tier quota
        # is a genuinely separate pool, so chaining across providers (not just across
        # Gemini keys) gives real headroom rather than doubling up on one rate limit.
        # NVIDIA first (best RPM seen among the free options, though unpublished/dynamic
        # so not fully guaranteed) -> Groq -> both Gemini keys -> Cerebras last (free
        # tier caps context at 8K tokens, too small for this app's later-turn prompts,
        # so it's a last resort rather than an equal peer).
        services: list = []
        if settings.nvidia_api_key:
            services.append(
                OpenAICompatLLMService(
                    base_url=_KNOWN_BYOK_BASE_URLS["nvidia"],
                    api_key=settings.nvidia_api_key,
                    model=settings.nvidia_model,
                )
            )
        if settings.groq_api_key:
            services.append(GroqLLMService())
        services.extend(
            OpenAICompatLLMService(
                base_url=_KNOWN_BYOK_BASE_URLS["gemini"],
                api_key=key,
                model=settings.gemini_model,
            )
            for key in gemini_keys
        )
        if settings.cerebras_api_key:
            services.append(
                OpenAICompatLLMService(
                    base_url=_KNOWN_BYOK_BASE_URLS["cerebras"],
                    api_key=settings.cerebras_api_key,
                    model=settings.cerebras_model,
                )
            )
        return services[0] if len(services) == 1 else FailoverLLMService(services)
    if settings.llm_provider == "mlx":
        from services.openai_compat_llm_service import OpenAICompatLLMService
        return OpenAICompatLLMService()
    return LLMService()


llm_service = _make_llm_service()


def _build_byok_service(
    provider: str, api_key: str, model_name: str | None, base_url: str | None
) -> "GroqLLMService | OpenAICompatLLMService":
    model = model_name or _DEFAULT_BYOK_MODELS.get(provider)

    if provider == "groq":
        from services.groq_llm_service import GroqLLMService
        return GroqLLMService(api_key=api_key, model=model)

    from services.openai_compat_llm_service import OpenAICompatLLMService
    resolved_base_url = base_url or _KNOWN_BYOK_BASE_URLS.get(provider)
    if not resolved_base_url:
        raise ValueError(
            f"No base_url known for provider {provider!r} — must be supplied at BYOK setup time"
        )
    return OpenAICompatLLMService(base_url=resolved_base_url, api_key=api_key, model=model)


async def resolve_llm_service(db, user_id, provider: str | None):
    """Returns the LLM service to use for a session: the user's stored BYOK key for
    `provider` if one exists, else the app default `llm_service` singleton (the path
    used by the alpha-tester/demo account and anyone without a stored key)."""
    if not provider:
        return llm_service

    from sqlalchemy import select
    from services import crypto_service
    from models.pg.user_api_key import UserAPIKey

    result = await db.execute(
        select(UserAPIKey).where(UserAPIKey.user_id == user_id, UserAPIKey.provider == provider)
    )
    key_row = result.scalar_one_or_none()
    if not key_row:
        return llm_service

    api_key = crypto_service.decrypt(key_row.encrypted_key)
    return _build_byok_service(provider, api_key, key_row.model_name, key_row.base_url)
