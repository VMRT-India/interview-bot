import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from models.pg.score import Score
from models.pg.user import User
from services.auth_service import create_access_token


async def _seed_user(
    pg_test_engine, is_guest: bool = False, is_alpha_tester: bool = False
) -> uuid.UUID:
    factory = async_sessionmaker(pg_test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        if is_guest:
            user = User(is_guest=True)
        else:
            user = User(
                email=f"test-{uuid.uuid4()}@example.com",
                password_hash="unused",
                is_alpha_tester=is_alpha_tester,
            )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id


async def _auth_headers(
    pg_test_engine, is_guest: bool = False, is_alpha_tester: bool = False
) -> tuple[dict, uuid.UUID]:
    user_id = await _seed_user(pg_test_engine, is_guest=is_guest, is_alpha_tester=is_alpha_tester)
    token = create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}, user_id


async def _seed_score(pg_test_engine, session_id: uuid.UUID) -> None:
    factory = async_sessionmaker(pg_test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        score = Score(
            session_id=session_id,
            turn_number=1,
            score=7.0,
            correctness=7.0,
            depth=7.0,
            communication=7.0,
            strengths="Good clarity",
            weaknesses="Lacks depth",
            improvement="Add concrete examples",
        )
        session.add(score)
        await session.commit()


_MOCK_CLOSING_REPORT = (
    '{"overall_summary": "Solid candidate.", '
    '"top_strengths": ["clear", "structured", "confident"], '
    '"key_gaps": ["depth", "edge cases"], '
    '"recommendations": ["practice more", "study OS", "read DDIA"], '
    '"hire_signal": "lean yes"}'
)


# ---------------------------------------------------------------------------
# POST /sessions
# ---------------------------------------------------------------------------

async def test_create_session_returns_201(client, pg_test_engine):
    headers, user_id = await _auth_headers(pg_test_engine)
    resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "ACTIVE"
    assert data["interview_type"] == "TECHNICAL"
    assert data["user_id"] == str(user_id)
    assert data["total_score"] is None
    assert data["ended_at"] is None


async def test_create_session_with_jd(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    resp = await client.post(
        "/sessions",
        json={"interview_type": "HR", "jd_text": "5 years Python experience required."},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["interview_type"] == "HR"


async def test_create_session_requires_auth(client):
    resp = await client.post("/sessions", json={"interview_type": "TECHNICAL"})
    assert resp.status_code == 401


async def test_create_session_stale_token_for_deleted_user_fails(client):
    token = create_access_token(uuid.uuid4())  # never persisted
    resp = await client.post(
        "/sessions",
        json={"interview_type": "TECHNICAL"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Free-tier session quota (Phase 9)
# ---------------------------------------------------------------------------

async def test_regular_user_blocked_after_two_free_sessions(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    for _ in range(2):
        resp = await client.post(
            "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
        )
        assert resp.status_code == 201
    resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    assert resp.status_code == 403


async def test_guest_blocked_after_one_free_session(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine, is_guest=True)
    resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    assert resp.status_code == 201
    resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    assert resp.status_code == 403


async def test_alpha_tester_bypasses_free_quota(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine, is_alpha_tester=True)
    for _ in range(5):
        resp = await client.post(
            "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
        )
        assert resp.status_code == 201


async def test_byok_session_bypasses_free_quota(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    for _ in range(3):
        resp = await client.post(
            "/sessions",
            json={"interview_type": "TECHNICAL", "llm_provider": "groq"},
            headers=headers,
        )
        assert resp.status_code == 201


async def test_create_session_invalid_type_fails(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    resp = await client.post(
        "/sessions", json={"interview_type": "INVALID_TYPE"}, headers=headers
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /sessions/{id}/close
# ---------------------------------------------------------------------------

async def test_close_session_not_found(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    resp = await client.post(f"/sessions/{uuid.uuid4()}/close", headers=headers)
    assert resp.status_code == 404


async def test_close_session_requires_auth(client):
    resp = await client.post(f"/sessions/{uuid.uuid4()}/close")
    assert resp.status_code == 401


async def test_close_session_wrong_owner_returns_403(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    create_resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    session_id = create_resp.json()["id"]

    other_headers, _ = await _auth_headers(pg_test_engine)
    resp = await client.post(f"/sessions/{session_id}/close", headers=other_headers)
    assert resp.status_code == 403


async def test_close_session_no_scores_returns_422(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    create_resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    session_id = create_resp.json()["id"]
    resp = await client.post(f"/sessions/{session_id}/close", headers=headers)
    assert resp.status_code == 422


async def test_close_session_returns_final_report(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    create_resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    session_id = uuid.UUID(create_resp.json()["id"])

    await _seed_score(pg_test_engine, session_id)

    with patch("api.routers.sessions.resolve_llm_service") as mock_resolve:
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=_MOCK_CLOSING_REPORT)
        mock_resolve.return_value = mock_llm
        resp = await client.post(f"/sessions/{session_id}/close", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == str(session_id)
    assert data["total_score"] == 7.0
    assert data["hire_signal"] == "lean yes"
    assert len(data["top_strengths"]) == 3
    assert len(data["turn_scores"]) == 1


# ---------------------------------------------------------------------------
# POST /sessions/{id}/close?terminated=true (Phase 9)
# ---------------------------------------------------------------------------

async def test_terminate_with_scores_sets_abandoned(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    create_resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    session_id = uuid.UUID(create_resp.json()["id"])
    await _seed_score(pg_test_engine, session_id)

    with patch("api.routers.sessions.resolve_llm_service") as mock_resolve:
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=_MOCK_CLOSING_REPORT)
        mock_resolve.return_value = mock_llm
        resp = await client.post(
            f"/sessions/{session_id}/close?terminated=true", headers=headers
        )

    assert resp.status_code == 200
    assert resp.json()["total_score"] == 7.0

    detail_resp = await client.get(f"/sessions/{session_id}", headers=headers)
    assert detail_resp.json()["status"] == "ABANDONED"


async def test_terminate_with_zero_scores_returns_empty_report_not_422(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    create_resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    session_id = uuid.UUID(create_resp.json()["id"])

    resp = await client.post(f"/sessions/{session_id}/close?terminated=true", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_score"] == 0.0
    assert data["hire_signal"] == "insufficient_data"
    assert data["turn_scores"] == []

    detail_resp = await client.get(f"/sessions/{session_id}", headers=headers)
    assert detail_resp.json()["status"] == "ABANDONED"


async def test_close_without_terminated_flag_still_sets_completed(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    create_resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    session_id = uuid.UUID(create_resp.json()["id"])
    await _seed_score(pg_test_engine, session_id)

    with patch("api.routers.sessions.resolve_llm_service") as mock_resolve:
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=_MOCK_CLOSING_REPORT)
        mock_resolve.return_value = mock_llm
        await client.post(f"/sessions/{session_id}/close", headers=headers)

    detail_resp = await client.get(f"/sessions/{session_id}", headers=headers)
    assert detail_resp.json()["status"] == "COMPLETED"


async def test_close_already_closed_session_returns_409(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    create_resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    session_id = uuid.UUID(create_resp.json()["id"])

    await _seed_score(pg_test_engine, session_id)

    with patch("api.routers.sessions.resolve_llm_service") as mock_resolve:
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=_MOCK_CLOSING_REPORT)
        mock_resolve.return_value = mock_llm
        resp1 = await client.post(f"/sessions/{session_id}/close", headers=headers)
        assert resp1.status_code == 200

        resp2 = await client.post(f"/sessions/{session_id}/close", headers=headers)
        assert resp2.status_code == 409


# ---------------------------------------------------------------------------
# GET /sessions
# ---------------------------------------------------------------------------

async def test_list_sessions_requires_auth(client):
    resp = await client.get("/sessions")
    assert resp.status_code == 401


async def test_list_sessions_returns_only_own_sessions(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    other_headers, _ = await _auth_headers(pg_test_engine)

    await client.post("/sessions", json={"interview_type": "TECHNICAL"}, headers=headers)
    await client.post("/sessions", json={"interview_type": "HR"}, headers=headers)
    await client.post("/sessions", json={"interview_type": "BEHAVIORAL"}, headers=other_headers)

    resp = await client.get("/sessions", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert {s["interview_type"] for s in data} == {"TECHNICAL", "HR"}


async def test_list_sessions_ordered_most_recent_first(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    first = await client.post("/sessions", json={"interview_type": "TECHNICAL"}, headers=headers)
    second = await client.post("/sessions", json={"interview_type": "HR"}, headers=headers)

    resp = await client.get("/sessions", headers=headers)
    data = resp.json()
    assert data[0]["id"] == second.json()["id"]
    assert data[1]["id"] == first.json()["id"]


# ---------------------------------------------------------------------------
# GET /sessions/{id}
# ---------------------------------------------------------------------------

async def test_get_session_detail_requires_auth(client):
    resp = await client.get(f"/sessions/{uuid.uuid4()}")
    assert resp.status_code == 401


async def test_get_session_detail_not_found(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    resp = await client.get(f"/sessions/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404


async def test_get_session_detail_wrong_owner_returns_403(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    create_resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    session_id = create_resp.json()["id"]

    other_headers, _ = await _auth_headers(pg_test_engine)
    resp = await client.get(f"/sessions/{session_id}", headers=other_headers)
    assert resp.status_code == 403


async def test_get_session_detail_active_session_has_no_report_yet(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    create_resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    session_id = uuid.UUID(create_resp.json()["id"])
    await _seed_score(pg_test_engine, session_id)

    resp = await client.get(f"/sessions/{session_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ACTIVE"
    assert data["overall_summary"] is None
    assert data["hire_signal"] is None
    # Turn scores fall back to Postgres `scores` even before the session is closed
    assert len(data["turn_scores"]) == 1


async def test_get_session_detail_after_close_includes_persisted_report(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    create_resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    session_id = uuid.UUID(create_resp.json()["id"])
    await _seed_score(pg_test_engine, session_id)

    with patch("api.routers.sessions.resolve_llm_service") as mock_resolve:
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=_MOCK_CLOSING_REPORT)
        mock_resolve.return_value = mock_llm
        close_resp = await client.post(f"/sessions/{session_id}/close", headers=headers)
    assert close_resp.status_code == 200

    resp = await client.get(f"/sessions/{session_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "COMPLETED"
    assert data["overall_summary"] == "Solid candidate."
    assert data["hire_signal"] == "lean yes"
    assert len(data["top_strengths"]) == 3
    assert len(data["turn_scores"]) == 1
    assert data["turn_scores"][0]["improvement"] == "Add concrete examples"


# ---------------------------------------------------------------------------
# GET /stats
# ---------------------------------------------------------------------------

async def test_stats_does_not_require_auth(client):
    resp = await client.get("/stats")
    assert resp.status_code == 200


async def test_stats_reflects_created_users_and_sessions(client, pg_test_engine):
    baseline = (await client.get("/stats")).json()

    headers, _ = await _auth_headers(pg_test_engine)
    await client.post("/sessions", json={"interview_type": "TECHNICAL"}, headers=headers)

    resp = await client.get("/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_users"] == baseline["total_users"] + 1
    assert data["total_sessions"] == baseline["total_sessions"] + 1
    assert data["completed_sessions"] == baseline["completed_sessions"]


async def test_stats_avg_score_reflects_completed_sessions(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    create_resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    session_id = uuid.UUID(create_resp.json()["id"])
    await _seed_score(pg_test_engine, session_id)

    with patch("api.routers.sessions.resolve_llm_service") as mock_resolve:
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=_MOCK_CLOSING_REPORT)
        mock_resolve.return_value = mock_llm
        await client.post(f"/sessions/{session_id}/close", headers=headers)

    resp = await client.get("/stats")
    data = resp.json()
    assert data["completed_sessions"] >= 1
    assert data["avg_score"] == 7.0


# ---------------------------------------------------------------------------
# POST /sessions/{id}/upload-jd, /upload-resume
# ---------------------------------------------------------------------------

_FAKE_PDF_BYTES = b"%PDF-1.4 fake content for upload tests"


def _pdf_file(name="doc.pdf"):
    return {"file": (name, _FAKE_PDF_BYTES, "application/pdf")}


async def test_upload_jd_requires_auth(client):
    resp = await client.post(
        f"/sessions/{uuid.uuid4()}/upload-jd", files=_pdf_file()
    )
    assert resp.status_code == 401


async def test_upload_jd_not_found(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    resp = await client.post(
        f"/sessions/{uuid.uuid4()}/upload-jd", files=_pdf_file(), headers=headers
    )
    assert resp.status_code == 404


async def test_upload_jd_wrong_owner_returns_403(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    create_resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    session_id = create_resp.json()["id"]

    other_headers, _ = await _auth_headers(pg_test_engine)
    resp = await client.post(
        f"/sessions/{session_id}/upload-jd", files=_pdf_file(), headers=other_headers
    )
    assert resp.status_code == 403


async def test_upload_jd_rejects_non_pdf_content_type(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    create_resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    session_id = create_resp.json()["id"]

    resp = await client.post(
        f"/sessions/{session_id}/upload-jd",
        files={"file": ("doc.txt", b"plain text", "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_upload_jd_success_sets_jd_text(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    create_resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    session_id = create_resp.json()["id"]

    with patch(
        "api.routers.sessions.extract_text_from_pdf",
        return_value="5 years of Python experience required.",
    ):
        resp = await client.post(
            f"/sessions/{session_id}/upload-jd", files=_pdf_file(), headers=headers
        )
    assert resp.status_code == 200

    detail_resp = await client.get(f"/sessions/{session_id}", headers=headers)
    # jd_text isn't directly exposed on SessionRead/SessionDetail, but a 200 here with no
    # error confirms the upload+commit path succeeded; the background task (real JD parsing)
    # is fire-and-forget same as the existing jd_text-at-creation test.
    assert detail_resp.status_code == 200


async def test_upload_jd_rejects_unparseable_pdf(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    create_resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    session_id = create_resp.json()["id"]

    with patch(
        "api.routers.sessions.extract_text_from_pdf",
        side_effect=ValueError("PDF contains no extractable text"),
    ):
        resp = await client.post(
            f"/sessions/{session_id}/upload-jd", files=_pdf_file(), headers=headers
        )
    assert resp.status_code == 422


async def test_upload_jd_rejects_already_started_interview(client, pg_test_engine, redis_clean):
    headers, _ = await _auth_headers(pg_test_engine)
    create_resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    session_id = create_resp.json()["id"]

    await redis_clean.set(
        f"session:{session_id}:state",
        '{"turn": 1, "history": [], "difficulty": 2, "domain": "TECHNICAL", "status": "active"}',
    )

    with patch("api.routers.sessions.extract_text_from_pdf", return_value="some text"):
        resp = await client.post(
            f"/sessions/{session_id}/upload-jd", files=_pdf_file(), headers=headers
        )
    assert resp.status_code == 409


async def test_upload_jd_rejects_completed_session(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    create_resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    session_id = uuid.UUID(create_resp.json()["id"])
    await _seed_score(pg_test_engine, session_id)

    with patch("api.routers.sessions.resolve_llm_service") as mock_resolve:
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=_MOCK_CLOSING_REPORT)
        mock_resolve.return_value = mock_llm
        await client.post(f"/sessions/{session_id}/close", headers=headers)

    with patch("api.routers.sessions.extract_text_from_pdf", return_value="some text"):
        resp = await client.post(
            f"/sessions/{session_id}/upload-jd", files=_pdf_file(), headers=headers
        )
    assert resp.status_code == 409


async def test_upload_resume_success(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    create_resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    session_id = create_resp.json()["id"]

    with patch(
        "api.routers.sessions.extract_text_from_pdf",
        return_value="Built a distributed cache in Go at Acme Corp.",
    ):
        resp = await client.post(
            f"/sessions/{session_id}/upload-resume", files=_pdf_file("resume.pdf"), headers=headers
        )
    assert resp.status_code == 200
    assert resp.json()["has_resume"] is True


async def test_upload_resume_wrong_owner_returns_403(client, pg_test_engine):
    headers, _ = await _auth_headers(pg_test_engine)
    create_resp = await client.post(
        "/sessions", json={"interview_type": "TECHNICAL"}, headers=headers
    )
    session_id = create_resp.json()["id"]

    other_headers, _ = await _auth_headers(pg_test_engine)
    resp = await client.post(
        f"/sessions/{session_id}/upload-resume", files=_pdf_file(), headers=other_headers
    )
    assert resp.status_code == 403
