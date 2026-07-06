from unittest.mock import AsyncMock, MagicMock, patch

from services.rag_service import RAGService, _build_chunk


# ---------------------------------------------------------------------------
# _build_chunk
# ---------------------------------------------------------------------------

def test_build_chunk_formats_correctly():
    doc = {"question": "What is a hash table?", "ideal_answer": "A key-value mapping structure."}
    assert _build_chunk(doc) == "Q: What is a hash table?\nA: A key-value mapping structure."


def test_build_chunk_handles_missing_fields():
    assert _build_chunk({}) == "Q: \nA: "


def test_build_chunk_partial_fields():
    doc = {"question": "What is recursion?"}
    assert _build_chunk(doc) == "Q: What is recursion?\nA: "


# ---------------------------------------------------------------------------
# RAGService.retrieve — failure paths
# ---------------------------------------------------------------------------

def _make_service() -> RAGService:
    service = RAGService.__new__(RAGService)
    service._embedder = AsyncMock()
    return service


async def test_retrieve_returns_empty_on_embed_failure():
    service = _make_service()
    service._embedder.embed.side_effect = RuntimeError("Ollama unreachable")
    result = await service.retrieve("test query", "TECHNICAL")
    assert result == []


async def test_retrieve_returns_empty_on_qdrant_failure():
    service = _make_service()
    service._embedder.embed.return_value = [0.1] * 768

    with patch("services.rag_service.get_qdrant") as mock_get_qdrant:
        mock_client = AsyncMock()
        mock_client.query_points.side_effect = RuntimeError("Qdrant down")
        mock_get_qdrant.return_value = mock_client

        result = await service.retrieve("test query", "TECHNICAL")

    assert result == []


# ---------------------------------------------------------------------------
# RAGService.retrieve — re-ranking correctness
# ---------------------------------------------------------------------------

def _make_hit(hit_id: str, score: float, text: str) -> MagicMock:
    h = MagicMock()
    h.id = hit_id
    h.score = score
    h.payload = {"text": text, "domain": "TECHNICAL"}
    return h


async def test_retrieve_ranking_orders_by_combined_score():
    """
    combined = 0.7 * cosine_score + 0.3 * (1 / (1 + l2_dist))
    where l2_dist = -euclid_score

    hit_A: cosine=0.9, euclid=-0.2  → 0.7*0.9 + 0.3*(1/1.2) = 0.630 + 0.250 = 0.880
    hit_B: cosine=0.5, euclid=-0.1  → 0.7*0.5 + 0.3*(1/1.1) = 0.350 + 0.273 = 0.623
    Expected order: A first, B second.
    """
    service = _make_service()
    service._embedder.embed.return_value = [0.0] * 768

    cosine_hits = [
        _make_hit("aaaa", 0.9, "text_A"),
        _make_hit("bbbb", 0.5, "text_B"),
    ]
    euclid_hits = [
        _make_hit("aaaa", -0.2, "text_A"),
        _make_hit("bbbb", -0.1, "text_B"),
    ]

    with patch("services.rag_service.get_qdrant"):
        with patch("services.rag_service._dual_search", new=AsyncMock(return_value=(cosine_hits, euclid_hits))):
            result = await service.retrieve("query", "TECHNICAL", top_k=2)

    assert result == ["text_A", "text_B"]


async def test_retrieve_respects_top_k():
    service = _make_service()
    service._embedder.embed.return_value = [0.0] * 768

    cosine_hits = [_make_hit(str(i), float(i) * 0.1, f"text_{i}") for i in range(10)]
    euclid_hits = [_make_hit(str(i), -float(i) * 0.05, f"text_{i}") for i in range(10)]

    with patch("services.rag_service.get_qdrant"):
        with patch("services.rag_service._dual_search", new=AsyncMock(return_value=(cosine_hits, euclid_hits))):
            result = await service.retrieve("query", "TECHNICAL", top_k=3)

    assert len(result) <= 3


async def test_retrieve_missing_text_payload_excluded():
    service = _make_service()
    service._embedder.embed.return_value = [0.0] * 768

    hit_no_text = MagicMock()
    hit_no_text.id = "xxxx"
    hit_no_text.score = 0.99
    hit_no_text.payload = {"domain": "TECHNICAL"}  # no "text" key

    cosine_hits = [hit_no_text]
    euclid_hits = []

    with patch("services.rag_service.get_qdrant"):
        with patch("services.rag_service._dual_search", new=AsyncMock(return_value=(cosine_hits, euclid_hits))):
            result = await service.retrieve("query", "TECHNICAL", top_k=3)

    assert result == []
