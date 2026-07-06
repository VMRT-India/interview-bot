import json
from unittest.mock import AsyncMock, patch

import pytest

from config import settings
from models.schemas.jd import JDParsed
from services.jd_service import (
    JDService,
    LLMKnowledgeProvider,
    _extract_json,
    _extract_json_array,
    _valid_doc,
)


# ---------------------------------------------------------------------------
# _extract_json / _extract_json_array
# ---------------------------------------------------------------------------

def test_extract_json_parses_clean_object():
    raw = '{"role_title": "Engineer", "domain": "TECHNICAL"}'
    result = _extract_json(raw)
    assert result["role_title"] == "Engineer"


def test_extract_json_strips_preamble():
    raw = 'Here you go:\n{"role_title": "SWE"}\nDone.'
    assert _extract_json(raw)["role_title"] == "SWE"


def test_extract_json_raises_on_no_object():
    with pytest.raises(ValueError, match="No JSON object"):
        _extract_json("no braces here")


def test_extract_json_array_parses_list():
    raw = '[{"topic": "Trees", "question": "Q?", "ideal_answer": "A.", "difficulty": 3}]'
    result = _extract_json_array(raw)
    assert len(result) == 1
    assert result[0]["topic"] == "Trees"


def test_extract_json_array_raises_on_no_array():
    with pytest.raises(ValueError, match="No JSON array"):
        _extract_json_array('{"not": "an array"}')


# ---------------------------------------------------------------------------
# _valid_doc
# ---------------------------------------------------------------------------

def test_valid_doc_accepts_complete_doc():
    doc = {"topic": "t", "question": "q", "ideal_answer": "a", "difficulty": 2}
    assert _valid_doc(doc) is True


def test_valid_doc_rejects_missing_field():
    doc = {"topic": "t", "question": "q", "ideal_answer": "a"}  # missing difficulty
    assert _valid_doc(doc) is False


def test_valid_doc_rejects_non_dict():
    assert _valid_doc("not a dict") is False


# ---------------------------------------------------------------------------
# JDService.parse_jd
# ---------------------------------------------------------------------------

_VALID_JD_RESPONSE = json.dumps({
    "role_title": "Senior Backend Engineer",
    "company_name": "Stripe",
    "seniority": "senior",
    "required_skills": ["Python", "PostgreSQL"],
    "preferred_skills": ["Kafka"],
    "tech_stack": ["FastAPI", "Redis"],
    "interview_focus": ["system design", "distributed systems"],
    "domain": "TECHNICAL",
})


async def test_parse_jd_returns_structured_model():
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value=_VALID_JD_RESPONSE)
    service = JDService(mock_llm)

    result = await service.parse_jd("Some JD text")

    assert isinstance(result, JDParsed)
    assert result.role_title == "Senior Backend Engineer"
    assert result.company_name == "Stripe"
    assert result.seniority == "senior"
    assert "Python" in result.required_skills
    assert result.domain == "TECHNICAL"


async def test_parse_jd_raises_on_llm_failure():
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
    service = JDService(mock_llm)

    with pytest.raises(RuntimeError):
        await service.parse_jd("Some JD text")


async def test_parse_jd_raises_on_malformed_json():
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value="not json at all")
    service = JDService(mock_llm)

    with pytest.raises(ValueError):
        await service.parse_jd("Some JD text")


# ---------------------------------------------------------------------------
# LLMKnowledgeProvider.generate
# ---------------------------------------------------------------------------

_VALID_GEN_RESPONSE = json.dumps({"questions": [
    {"topic": "Trees", "question": "Explain BST.", "ideal_answer": "Binary search tree.", "difficulty": 2},
    {"topic": "Graphs", "question": "BFS vs DFS?", "ideal_answer": "BFS uses queue, DFS uses stack.", "difficulty": 3},
]})

_JD_PARSED = JDParsed(
    role_title="Backend Engineer",
    company_name="Acme",
    required_skills=["Python", "SQL"],
    tech_stack=["FastAPI"],
    domain="TECHNICAL",
)


async def test_generate_returns_valid_docs():
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value=_VALID_GEN_RESPONSE)
    provider = LLMKnowledgeProvider(mock_llm)

    result = await provider.generate(_JD_PARSED)

    assert len(result) == 2
    assert result[0]["topic"] == "Trees"
    assert result[1]["question"] == "BFS vs DFS?"


async def test_generate_filters_invalid_docs():
    invalid_response = json.dumps({"questions": [
        {"topic": "T", "question": "Q?", "ideal_answer": "A."},  # missing difficulty → filtered
        {"topic": "T2", "question": "Q2?", "ideal_answer": "A2.", "difficulty": 1},
    ]})
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value=invalid_response)
    provider = LLMKnowledgeProvider(mock_llm)

    result = await provider.generate(_JD_PARSED)

    assert len(result) == 1
    assert result[0]["topic"] == "T2"


async def test_generate_returns_empty_on_llm_failure():
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM down"))
    provider = LLMKnowledgeProvider(mock_llm)

    result = await provider.generate(_JD_PARSED)

    assert result == []


async def test_generate_count_scales_with_skills():
    """Count = min(max(8, len(required_skills + tech_stack) * 2), 12)"""
    captured_prompts = []

    mock_llm = AsyncMock()

    async def capture_generate(prompt, **kwargs):
        captured_prompts.append(prompt)
        return _VALID_GEN_RESPONSE

    mock_llm.generate = capture_generate
    provider = LLMKnowledgeProvider(mock_llm)

    # 8 skills → count = max(8, 8*2) = 16, capped at 12 → 12
    big_jd = JDParsed(
        role_title="Lead Engineer",
        required_skills=["Python", "Go", "Rust", "C++"],
        tech_stack=["Kafka", "Redis", "PostgreSQL", "Kubernetes"],
        domain="TECHNICAL",
    )
    await provider.generate(big_jd)

    assert "12" in captured_prompts[0]


# ---------------------------------------------------------------------------
# resolve_target_minutes — JD-stated -> Tavily-researched -> default
# ---------------------------------------------------------------------------

async def test_resolve_target_minutes_prefers_jd_stated_duration():
    service = JDService(AsyncMock())
    jd_parsed = JDParsed(role_title="Engineer", company_name="Acme", estimated_duration_minutes=30)

    with patch(
        "services.jd_service.company_lookup_service.search_interview_duration",
        new=AsyncMock(return_value=999),
    ) as mock_search:
        result = await service.resolve_target_minutes(jd_parsed)

    assert result == 30
    mock_search.assert_not_called()


async def test_resolve_target_minutes_falls_back_to_company_research():
    service = JDService(AsyncMock())
    jd_parsed = JDParsed(role_title="Engineer", company_name="Acme")

    with patch(
        "services.jd_service.company_lookup_service.search_interview_duration",
        new=AsyncMock(return_value=60),
    ):
        result = await service.resolve_target_minutes(jd_parsed)

    assert result == 60


async def test_resolve_target_minutes_falls_back_to_default_when_no_signal():
    service = JDService(AsyncMock())
    jd_parsed = JDParsed(role_title="Engineer", company_name="Acme")

    with patch(
        "services.jd_service.company_lookup_service.search_interview_duration",
        new=AsyncMock(return_value=None),
    ):
        result = await service.resolve_target_minutes(jd_parsed)

    assert result == settings.default_interview_target_minutes


async def test_resolve_target_minutes_no_jd_uses_default():
    service = JDService(AsyncMock())
    result = await service.resolve_target_minutes(None)
    assert result == settings.default_interview_target_minutes
