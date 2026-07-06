"""
WebSocket integration tests.

Uses Starlette's TestClient (sync) for WebSocket protocol testing.
All external services (LLM, RAG, Redis, scoring, transcript, Qdrant) are mocked —
this layer tests the WS message protocol, state transitions, and session validation.
"""
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.testclient import TestClient

from services.auth_service import create_access_token

_TEST_USER_ID = uuid.uuid4()
_TEST_TOKEN = create_access_token(_TEST_USER_ID)


@contextmanager
def _app_client():
    """TestClient that patches lifespan calls that would fail in a thread-local loop."""
    from main import app
    with (
        patch("db.qdrant.init_collection", new=AsyncMock()),
        patch("db.qdrant.close", new=AsyncMock()),
        patch("db.redis.close", new=AsyncMock()),
    ):
        with TestClient(app) as tc:
            yield tc


def _make_fake_session(session_id=None, active=True, user_id=None):
    from models.pg.session import InterviewType, SessionStatus
    session = MagicMock()
    session.id = session_id or uuid.uuid4()
    session.status = SessionStatus.ACTIVE if active else SessionStatus.COMPLETED
    session.interview_type = InterviewType.TECHNICAL
    session.jd_text = None
    session.resume_text = None
    session.target_minutes = 45
    session.started_at = datetime.now(timezone.utc)
    session.user_id = user_id or _TEST_USER_ID
    return session


async def _fake_stream(*args, **kwargs):
    for token in ["What", " is", " a", " hash", " table", "?"]:
        yield token


def _build_redis_mock():
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock()
    redis_mock.ping = AsyncMock(return_value=True)
    return redis_mock


def _fake_session_factory():
    """Mimics AsyncSessionFactory() used as `async with AsyncSessionFactory() as db:` —
    resolve_llm_service is mocked separately, so the yielded db object is never used."""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=MagicMock())
    cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=cm)


# ---------------------------------------------------------------------------
# Invalid session
# ---------------------------------------------------------------------------

def test_ws_error_on_missing_session():
    with patch("api.routers.interview_ws._load_session", new=AsyncMock(return_value=None)):
        with _app_client() as tc:
            with tc.websocket_connect(f"/ws/interview/{uuid.uuid4()}?token={_TEST_TOKEN}") as ws:
                msg = ws.receive_json()
    assert msg["type"] == "error"
    assert "not found" in msg["content"].lower()


def test_ws_error_on_completed_session():
    fake = _make_fake_session(active=False)
    with patch("api.routers.interview_ws._load_session", new=AsyncMock(return_value=fake)):
        with _app_client() as tc:
            with tc.websocket_connect(f"/ws/interview/{fake.id}?token={_TEST_TOKEN}") as ws:
                msg = ws.receive_json()
    assert msg["type"] == "error"


def test_ws_error_on_missing_token():
    with _app_client() as tc:
        with tc.websocket_connect(f"/ws/interview/{uuid.uuid4()}") as ws:
            msg = ws.receive_json()
    assert msg["type"] == "error"
    assert "token" in msg["content"].lower()


def test_ws_error_on_wrong_owner():
    fake = _make_fake_session(user_id=uuid.uuid4())  # not _TEST_USER_ID
    with patch("api.routers.interview_ws._load_session", new=AsyncMock(return_value=fake)):
        with _app_client() as tc:
            with tc.websocket_connect(f"/ws/interview/{fake.id}?token={_TEST_TOKEN}") as ws:
                msg = ws.receive_json()
    assert msg["type"] == "error"
    assert "not your session" in msg["content"].lower()


# ---------------------------------------------------------------------------
# Valid session: one full turn → session_end
# ---------------------------------------------------------------------------

def test_ws_streams_tokens_and_ends_session():
    session_id = uuid.uuid4()
    fake_session = _make_fake_session(session_id=session_id)

    mock_llm = MagicMock()
    mock_llm.stream_generate = _fake_stream

    with (
        patch("api.routers.interview_ws._load_session", new=AsyncMock(return_value=fake_session)),
        patch("api.routers.interview_ws.rag_service") as mock_rag,
        patch("api.routers.interview_ws.resolve_llm_service", new=AsyncMock(return_value=mock_llm)),
        patch("api.routers.interview_ws.AsyncSessionFactory", new=_fake_session_factory()),
        patch("api.routers.interview_ws._get_target_minutes", new=AsyncMock(return_value=45)),
        patch("api.routers.interview_ws.score_turn", new=AsyncMock(return_value=None)),
        patch("api.routers.interview_ws._append_transcript", new=AsyncMock()),
        patch("api.routers.interview_ws.get_redis", return_value=_build_redis_mock()),
        patch("api.routers.interview_ws.settings") as mock_settings,
    ):
        mock_rag.retrieve = AsyncMock(return_value=["Q: What is a hash?\nA: A mapping."])
        mock_settings.max_interview_turns = 1

        with _app_client() as tc:
            with tc.websocket_connect(f"/ws/interview/{session_id}?token={_TEST_TOKEN}") as ws:
                received = []

                while True:
                    msg = ws.receive_json()
                    received.append(msg)
                    if msg["type"] in ("question_end", "error", "session_end"):
                        break

                assert any(m["type"] == "token" for m in received)
                assert received[-1]["type"] == "question_end"

                ws.send_json({"content": "A hash table maps keys to values using a hash function."})

                # max_interview_turns=1 forces closing on the next loop iteration: the server
                # streams one final in-character sign-off (same token/question_end protocol)
                # before session_end — never an abrupt raw cutoff.
                closing_received = []
                while True:
                    msg = ws.receive_json()
                    closing_received.append(msg)
                    if msg["type"] == "session_end":
                        break

                assert any(m["type"] == "token" for m in closing_received)
                assert closing_received[-1]["type"] == "session_end"


# ---------------------------------------------------------------------------
# Message protocol: token messages are non-empty strings
# ---------------------------------------------------------------------------

def test_ws_token_messages_are_non_empty_strings():
    session_id = uuid.uuid4()
    fake_session = _make_fake_session(session_id=session_id)

    mock_llm = MagicMock()
    mock_llm.stream_generate = _fake_stream

    with (
        patch("api.routers.interview_ws._load_session", new=AsyncMock(return_value=fake_session)),
        patch("api.routers.interview_ws.rag_service") as mock_rag,
        patch("api.routers.interview_ws.resolve_llm_service", new=AsyncMock(return_value=mock_llm)),
        patch("api.routers.interview_ws.AsyncSessionFactory", new=_fake_session_factory()),
        patch("api.routers.interview_ws._get_target_minutes", new=AsyncMock(return_value=45)),
        patch("api.routers.interview_ws.score_turn", new=AsyncMock(return_value=None)),
        patch("api.routers.interview_ws._append_transcript", new=AsyncMock()),
        patch("api.routers.interview_ws.get_redis", return_value=_build_redis_mock()),
        patch("api.routers.interview_ws.settings") as mock_settings,
    ):
        mock_rag.retrieve = AsyncMock(return_value=[])
        mock_settings.max_interview_turns = 1

        with _app_client() as tc:
            with tc.websocket_connect(f"/ws/interview/{session_id}?token={_TEST_TOKEN}") as ws:
                tokens = []
                while True:
                    msg = ws.receive_json()
                    if msg["type"] == "token":
                        tokens.append(msg["content"])
                    elif msg["type"] == "question_end":
                        break

                ws.send_json({"content": "My answer."})
                while True:
                    msg = ws.receive_json()
                    if msg["type"] == "token":
                        tokens.append(msg["content"])
                    elif msg["type"] == "session_end":
                        break

    assert len(tokens) > 0
    assert all(isinstance(t, str) and len(t) > 0 for t in tokens)
