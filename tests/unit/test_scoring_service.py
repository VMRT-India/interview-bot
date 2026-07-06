import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.scoring_service import _extract_json, score_turn


# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------

def test_extract_json_clean_object():
    raw = '{"correctness": 8.0, "depth": 7.0, "score": 7.5}'
    result = _extract_json(raw)
    assert result["correctness"] == 8.0
    assert result["score"] == 7.5


def test_extract_json_with_preamble_and_postamble():
    raw = 'Here is the evaluation:\n{"depth": 6.0, "score": 6.0}\nEnd of response.'
    result = _extract_json(raw)
    assert result["depth"] == 6.0


def test_extract_json_no_braces_raises():
    with pytest.raises(ValueError, match="No JSON object"):
        _extract_json("No JSON here at all.")


def test_extract_json_malformed_raises():
    with pytest.raises(Exception):
        _extract_json("{not valid json}")


# ---------------------------------------------------------------------------
# score_turn
# ---------------------------------------------------------------------------

_VALID_LLM_RESPONSE = (
    '{"correctness": 8.0, "depth": 7.0, "communication": 9.0, "score": 7.95, '
    '"strengths": "clear explanation", "weaknesses": "lacks depth", '
    '"improvement": "add concrete examples"}'
)


async def test_score_turn_returns_none_on_llm_failure():
    with patch("services.scoring_service.llm_service") as mock_llm:
        mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        result = await score_turn(uuid.uuid4(), 1, "What is O(n)?", "Linear time.")
    assert result is None


async def test_score_turn_returns_none_on_invalid_json():
    with patch("services.scoring_service.llm_service") as mock_llm:
        mock_llm.generate = AsyncMock(return_value="Not JSON at all.")
        result = await score_turn(uuid.uuid4(), 1, "Question?", "Answer.")
    assert result is None


async def test_score_turn_parses_and_returns_result():
    # Use MagicMock for session so db.add() is sync (as SQLAlchemy expects)
    mock_db_session = MagicMock()
    mock_db_session.commit = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("services.scoring_service.llm_service") as mock_llm,
        patch("services.scoring_service.AsyncSessionFactory", return_value=mock_ctx),
    ):
        mock_llm.generate = AsyncMock(return_value=_VALID_LLM_RESPONSE)
        result = await score_turn(uuid.uuid4(), 1, "What is O(n)?", "Linear time complexity.")

    assert result is not None
    assert result.score == 7.95
    assert result.correctness == 8.0
    assert result.depth == 7.0
    assert result.communication == 9.0
    assert result.strengths == "clear explanation"
    assert result.weaknesses == "lacks depth"


async def test_score_turn_db_write_failure_still_returns_result():
    """LLM parse succeeds but DB write fails — result is still returned."""
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("DB connection error"))
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("services.scoring_service.llm_service") as mock_llm,
        patch("services.scoring_service.AsyncSessionFactory", return_value=mock_ctx),
    ):
        mock_llm.generate = AsyncMock(return_value=_VALID_LLM_RESPONSE)
        result = await score_turn(uuid.uuid4(), 1, "What is O(n)?", "Linear time.")

    assert result is not None
    assert result.score == 7.95
