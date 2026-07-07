import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.embedding_service import (
    FailoverEmbeddingProvider,
    HuggingFaceEmbeddingProvider,
    OllamaEmbeddingProvider,
    get_embedding_service,
)


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


def _mock_httpx_response(vector):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=vector)
    return resp


async def test_hf_embed_returns_correct_dimension(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "hf_api_token", "test-token")
    monkeypatch.setattr(config.settings, "hf_embedding_model", "BAAI/bge-base-en-v1.5")
    provider = HuggingFaceEmbeddingProvider()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_mock_httpx_response([0.1] * 768))
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("services.embedding_service.httpx.AsyncClient", return_value=mock_ctx):
        result = await provider.embed("test text")
    assert len(result) == 768


async def test_hf_embed_unwraps_nested_response(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "hf_api_token", "test-token")
    provider = HuggingFaceEmbeddingProvider()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_mock_httpx_response([[0.2] * 768]))
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("services.embedding_service.httpx.AsyncClient", return_value=mock_ctx):
        result = await provider.embed("test text")
    assert len(result) == 768


async def test_hf_embed_dim_mismatch_raises(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "hf_api_token", "test-token")
    provider = HuggingFaceEmbeddingProvider()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_mock_httpx_response([0.1] * 100))
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("services.embedding_service.httpx.AsyncClient", return_value=mock_ctx):
        with pytest.raises(ValueError, match="dim mismatch"):
            await provider.embed("test text")


async def test_failover_embedding_uses_first_provider_on_success():
    primary = _make_provider([0.1] * 768)
    fallback = _make_provider([0.2] * 768)
    failover = FailoverEmbeddingProvider([primary, fallback])
    result = await failover.embed("text")
    assert result == [0.1] * 768
    assert fallback._client.embeddings.call_count == 0


async def test_failover_embedding_falls_back_on_failure():
    primary = OllamaEmbeddingProvider.__new__(OllamaEmbeddingProvider)
    primary._client = AsyncMock()
    primary._client.embeddings = AsyncMock(side_effect=RuntimeError("HF down"))
    fallback = _make_provider([0.3] * 768)
    failover = FailoverEmbeddingProvider([primary, fallback])
    result = await failover.embed("text")
    assert result == [0.3] * 768


async def test_failover_embedding_raises_if_all_fail():
    a = OllamaEmbeddingProvider.__new__(OllamaEmbeddingProvider)
    a._client = AsyncMock()
    a._client.embeddings = AsyncMock(side_effect=RuntimeError("a down"))
    b = OllamaEmbeddingProvider.__new__(OllamaEmbeddingProvider)
    b._client = AsyncMock()
    b._client.embeddings = AsyncMock(side_effect=RuntimeError("b down"))
    failover = FailoverEmbeddingProvider([a, b])
    with pytest.raises(RuntimeError, match="b down"):
        await failover.embed("text")


def test_failover_embedding_requires_at_least_one_provider():
    with pytest.raises(ValueError):
        FailoverEmbeddingProvider([])


def test_factory_returns_ollama_provider(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "embedding_provider", "ollama")
    assert isinstance(get_embedding_service(), OllamaEmbeddingProvider)


def test_factory_returns_failover_for_huggingface(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "embedding_provider", "huggingface")
    monkeypatch.setattr(config.settings, "hf_api_token", "test-token")
    service = get_embedding_service()
    assert isinstance(service, FailoverEmbeddingProvider)
    assert isinstance(service._providers[0], HuggingFaceEmbeddingProvider)
    assert isinstance(service._providers[1], OllamaEmbeddingProvider)


def test_factory_unknown_provider_raises(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "embedding_provider", "unknown")
    with pytest.raises(ValueError, match="Unknown embedding provider"):
        get_embedding_service()
