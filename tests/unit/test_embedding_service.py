import pytest
from unittest.mock import AsyncMock

from services.embedding_service import OllamaEmbeddingProvider


def _make_provider(embedding: list[float]) -> OllamaEmbeddingProvider:
    provider = OllamaEmbeddingProvider.__new__(OllamaEmbeddingProvider)
    provider._client = AsyncMock()
    provider._client.embeddings.return_value = {"embedding": embedding}
    return provider


async def test_embed_returns_correct_dimension():
    provider = _make_provider([0.1] * 768)
    result = await provider.embed("test text")
    assert len(result) == 768


async def test_embed_dim_mismatch_raises_value_error():
    provider = _make_provider([0.1] * 100)  # wrong dim
    with pytest.raises(ValueError, match="dim mismatch"):
        await provider.embed("test text")


async def test_embed_calls_ollama_with_correct_model():
    provider = _make_provider([0.0] * 768)
    await provider.embed("some text")
    call_kwargs = provider._client.embeddings.call_args
    assert call_kwargs is not None
    assert "nomic-embed-text" in str(call_kwargs)


async def test_embed_batch_returns_one_vector_per_text():
    provider = _make_provider([0.5] * 768)
    texts = ["text one", "text two", "text three"]
    results = await provider.embed_batch(texts)
    assert len(results) == 3
    assert all(len(v) == 768 for v in results)


async def test_embed_batch_calls_embed_concurrently():
    provider = _make_provider([0.0] * 768)
    await provider.embed_batch(["a", "b", "c"])
    assert provider._client.embeddings.call_count == 3
