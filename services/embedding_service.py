import asyncio
from abc import ABC, abstractmethod

import ollama

from config import settings


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]: ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


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


def get_embedding_service() -> EmbeddingProvider:
    if settings.embedding_provider == "ollama":
        return OllamaEmbeddingProvider()
    raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")
