import asyncio

import httpx
import ollama
import structlog
from abc import ABC, abstractmethod

from config import settings

logger = structlog.get_logger()


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]: ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    async def health_check(self) -> bool: ...


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        self._client = ollama.AsyncClient(host=settings.ollama_host)

    async def embed(self, text: str) -> list[float]:
        response = await self._client.embeddings(
            model=settings.embedding_model, prompt=text
        )
        vector = response["embedding"]
        if len(vector) != settings.embedding_dim:
            raise ValueError(
                f"Embedding dim mismatch: expected {settings.embedding_dim}, got {len(vector)}"
            )
        return vector

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return list(await asyncio.gather(*[self.embed(t) for t in texts]))

    async def health_check(self) -> bool:
        try:
            await self._client.list()
            return True
        except Exception:
            return False


class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    """Calls HF's free Inference Providers API for settings.hf_embedding_model.
    Default is BAAI/bge-base-en-v1.5 (768-dim, live on the free "hf-inference"
    provider) — NOT nomic-embed-text-v1.5, which was live-verified this session
    to have zero active inference providers (empty inferenceProviderMapping via
    HF's own API) despite being downloadable; bge-base is a comparable-quality
    substitute with the same 768 dimensions, so no Qdrant/config dimension
    change is needed. No local process, no RAM footprint on this app's own host."""

    _URL_TEMPLATE = "https://router.huggingface.co/hf-inference/models/{model}"

    def __init__(self) -> None:
        self._url = self._URL_TEMPLATE.format(model=settings.hf_embedding_model)
        self._headers = {"Authorization": f"Bearer {settings.hf_api_token}"}

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self._url, headers=self._headers, json={"inputs": text}
            )
            response.raise_for_status()
            vector = response.json()
            # feature-extraction can return a nested [[...]] for some pipelines
            if vector and isinstance(vector[0], list):
                vector = vector[0]
        if len(vector) != settings.embedding_dim:
            raise ValueError(
                f"Embedding dim mismatch: expected {settings.embedding_dim}, got {len(vector)}"
            )
        return vector

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return list(await asyncio.gather(*[self.embed(t) for t in texts]))

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"https://huggingface.co/api/models/{settings.hf_embedding_model}",
                    headers=self._headers,
                )
                return response.status_code == 200
        except Exception:
            return False


class FailoverEmbeddingProvider(EmbeddingProvider):
    """Tries each provider in order, falling over to the next on any failure.
    Used to keep Ollama as a local-dev / emergency fallback behind the new
    HF-hosted default — harmless in production where Ollama isn't running
    (fails through quickly, same graceful-degradation path RAGService already
    has for a total embedding failure)."""

    def __init__(self, providers: list[EmbeddingProvider]) -> None:
        if not providers:
            raise ValueError("FailoverEmbeddingProvider needs at least one provider")
        self._providers = providers

    async def embed(self, text: str) -> list[float]:
        last_exc: Exception | None = None
        for provider in self._providers:
            try:
                return await provider.embed(text)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "embedding_failover", provider=type(provider).__name__, error=str(exc)
                )
        raise last_exc  # type: ignore[misc]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return list(await asyncio.gather(*[self.embed(t) for t in texts]))

    async def health_check(self) -> bool:
        for provider in self._providers:
            if await provider.health_check():
                return True
        return False


def get_embedding_service() -> EmbeddingProvider:
    if settings.embedding_provider == "ollama":
        return OllamaEmbeddingProvider()
    if settings.embedding_provider == "huggingface":
        return FailoverEmbeddingProvider(
            [HuggingFaceEmbeddingProvider(), OllamaEmbeddingProvider()]
        )
    raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")
