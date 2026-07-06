import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.routers.interview_ws import _get_target_minutes, _should_close
from config import settings

_HISTORY = [{"question": "Explain hashing.", "answer": "Maps keys to buckets."}]


@pytest.mark.asyncio
async def test_should_close_false_when_under_target():
    llm = AsyncMock()
    result = await _should_close(10.0, 45, 3, _HISTORY, llm, MagicMock())
    assert result is False
    llm.generate.assert_not_called()


@pytest.mark.asyncio
async def test_should_close_true_when_past_overrun_ceiling():
    llm = AsyncMock()
    # target 45 * overrun 1.3 = 58.5 -> 60 min is past the ceiling
    result = await _should_close(60.0, 45, 3, _HISTORY, llm, MagicMock())
    assert result is True
    llm.generate.assert_not_called()


@pytest.mark.asyncio
async def test_should_close_asks_llm_between_target_and_ceiling():
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value='{"conclude": true}')
    # target 45, ceiling 58.5 -> 50 min is in the judgment window
    result = await _should_close(50.0, 45, 3, _HISTORY, llm, MagicMock())
    assert result is True
    llm.generate.assert_called_once()


@pytest.mark.asyncio
async def test_should_close_llm_says_continue():
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value='{"conclude": false}')
    result = await _should_close(50.0, 45, 3, _HISTORY, llm, MagicMock())
    assert result is False


@pytest.mark.asyncio
async def test_should_close_defaults_to_continue_on_llm_failure():
    llm = AsyncMock()
    llm.generate = AsyncMock(side_effect=RuntimeError("boom"))
    result = await _should_close(50.0, 45, 3, _HISTORY, llm, MagicMock())
    assert result is False


@pytest.mark.asyncio
async def test_should_close_no_history_never_closes_early():
    llm = AsyncMock()
    result = await _should_close(50.0, 45, 0, [], llm, MagicMock())
    assert result is False
    llm.generate.assert_not_called()


@pytest.mark.asyncio
async def test_should_close_true_when_turn_hits_absolute_cap():
    llm = AsyncMock()
    result = await _should_close(1.0, 45, settings.max_interview_turns, _HISTORY, llm, MagicMock())
    assert result is True
    llm.generate.assert_not_called()


def _fake_session_factory_returning(value):
    """Mimics `async with AsyncSessionFactory() as db:` where db.execute(...).scalar_one_or_none()
    returns `value` — used to verify _get_target_minutes re-queries fresh each call rather than
    caching a stale value from before a background resolution task commits."""
    db = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none = MagicMock(return_value=value)
    db.execute = AsyncMock(return_value=exec_result)
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=cm)


@pytest.mark.asyncio
async def test_get_target_minutes_reflects_latest_committed_value():
    """Regression test: target_minutes must be re-read from Postgres on every call, not cached
    from the WS-connect-time session snapshot — otherwise a background JD-parsing task that
    resolves the real target *after* the WS has already connected would silently be ignored for
    the rest of the interview (observed live: a session created with a JD stating '45 minute
    interview' kept using the pre-resolution default the whole time)."""
    session_id = uuid.uuid4()

    with patch(
        "api.routers.interview_ws.AsyncSessionFactory",
        new=_fake_session_factory_returning(1),
    ):
        assert await _get_target_minutes(session_id) == 1

    with patch(
        "api.routers.interview_ws.AsyncSessionFactory",
        new=_fake_session_factory_returning(45),
    ):
        assert await _get_target_minutes(session_id) == 45
