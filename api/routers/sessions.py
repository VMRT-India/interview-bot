import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from config import settings
from db.mongo import session_reports_col, sessions_col
from db.postgres import AsyncSessionFactory, get_db
from db.redis import get_redis
from models.pg.score import Score
from models.pg.session import Session, SessionStatus
from models.pg.user import User
from models.schemas.score import ScoreRead
from models.schemas.session import FinalReport, SessionCreate, SessionDetail, SessionRead
from prompts.closing import SYSTEM_PROMPT as CLOSING_SYSTEM, build_closing_prompt
from services.file_extraction_service import extract_text_from_pdf
from services.jd_service import jd_service, knowledge_provider
from services.json_utils import extract_json as _extract_json
from services.llm_service import resolve_llm_service
from services.rag_service import rag_service

router = APIRouter(prefix="/sessions")
logger = structlog.get_logger()

# Sessions using the shared app-default LLM key (no BYOK provider chosen) are capped
# per account so the app's own key isn't burned unlimited by every signed-up user.
# Guests get a tighter cap since they're not a durable identity. Alpha testers and any
# session with body.llm_provider set (BYOK) bypass this entirely.
_FREE_SESSION_LIMIT_GUEST = 1
_FREE_SESSION_LIMIT_REGULAR = 2


async def _prepare_jd_knowledge(session_id: uuid.UUID, jd_text: str, jd_hash: str) -> None:
    """Background task: parses the JD, resolves the interview's target duration (JD-stated ->
    Tavily-researched -> default), persists both, then ensures RAG knowledge exists for this JD.
    Runs after session creation OR a post-creation JD upload — same pipeline either way."""
    log = logger.bind(jd_hash=jd_hash, session_id=str(session_id))
    try:
        jd_parsed = await jd_service.parse_jd(jd_text)
        await get_redis().set(
            f"jd:{jd_hash}:parsed",
            jd_parsed.model_dump_json(),
            ex=86400,
        )

        target_minutes = await jd_service.resolve_target_minutes(jd_parsed)
        async with AsyncSessionFactory() as db:
            result = await db.execute(select(Session).where(Session.id == session_id))
            session = result.scalar_one_or_none()
            if session:
                session.target_minutes = target_minutes
                await db.commit()
        log.info("target_minutes_resolved", target_minutes=target_minutes)

        if await rag_service.has_jd_documents(jd_hash):
            log.info("jd_knowledge_already_indexed")
            return
        docs = await knowledge_provider.generate(jd_parsed)
        if docs:
            count = await rag_service.ingest_jd_documents(jd_hash, docs, jd_parsed.domain)
            log.info("jd_knowledge_ingested", count=count)
        else:
            log.warning("jd_knowledge_gen_empty")
    except Exception as exc:
        log.warning("jd_prepare_failed", error=str(exc))


@router.post("", response_model=SessionRead, status_code=201)
async def create_session(
    body: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not body.llm_provider and not current_user.is_alpha_tester:
        limit = (
            _FREE_SESSION_LIMIT_GUEST if current_user.is_guest else _FREE_SESSION_LIMIT_REGULAR
        )
        if current_user.free_sessions_used >= limit:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Free session limit reached. Add your own API key in Settings to "
                    "keep using the app, or sign up if you're on a guest trial."
                ),
            )
        current_user.free_sessions_used += 1

    session = Session(
        user_id=current_user.id,
        interview_type=body.interview_type,
        jd_text=body.jd_text,
        llm_provider=body.llm_provider,
        # No JD to research a duration from — use the configured default immediately.
        # Overwritten by _prepare_jd_knowledge() below once JD parsing resolves a real target.
        target_minutes=settings.default_interview_target_minutes,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    logger.info("session_created", session_id=str(session.id))

    if body.jd_text:
        jd_hash = hashlib.sha256(body.jd_text.encode()).hexdigest()
        asyncio.create_task(_prepare_jd_knowledge(session.id, body.jd_text, jd_hash))

    return session


@router.get("", response_model=list[SessionRead])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Session)
        .where(Session.user_id == current_user.id)
        .order_by(Session.started_at.desc())
    )
    return list(result.scalars().all())


async def _load_owned_active_session(
    session_id: uuid.UUID, db: AsyncSession, current_user: User
) -> Session:
    """Shared guard for the upload endpoints: must exist, must be owned by the caller, must
    still be ACTIVE, and — since interview_ws.py only reads jd_text/resume_text once at WS
    connect time — must not have started yet (turn 0), or the upload would silently have no
    effect on an in-progress interview."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your session")
    if session.status != SessionStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Session is not active")

    raw_state = await get_redis().get(f"session:{session_id}:state")
    if raw_state:
        if json.loads(raw_state).get("turn", 0) > 0:
            raise HTTPException(
                status_code=409,
                detail="Interview already in progress — upload before starting the interview",
            )
    return session


async def _read_pdf_upload(file: UploadFile) -> str:
    if file.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are supported")
    raw = await file.read()
    try:
        return extract_text_from_pdf(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/{session_id}/upload-jd", response_model=SessionRead)
async def upload_jd(
    session_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await _load_owned_active_session(session_id, db, current_user)
    jd_text = await _read_pdf_upload(file)

    session.jd_text = jd_text
    await db.commit()
    await db.refresh(session)

    jd_hash = hashlib.sha256(jd_text.encode()).hexdigest()
    asyncio.create_task(_prepare_jd_knowledge(session.id, jd_text, jd_hash))
    logger.info("jd_uploaded", session_id=str(session_id))
    return session


@router.post("/{session_id}/upload-resume", response_model=SessionRead)
async def upload_resume(
    session_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await _load_owned_active_session(session_id, db, current_user)
    session.resume_text = await _read_pdf_upload(file)
    await db.commit()
    await db.refresh(session)
    logger.info("resume_uploaded", session_id=str(session_id))
    return session


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your session")

    detail = SessionDetail.model_validate(session)

    report_doc = await session_reports_col().find_one({"session_id": str(session_id)})
    if report_doc:
        detail.overall_summary = report_doc.get("overall_summary")
        detail.top_strengths = report_doc.get("top_strengths", [])
        detail.key_gaps = report_doc.get("key_gaps", [])
        detail.recommendations = report_doc.get("recommendations", [])
        detail.hire_signal = report_doc.get("hire_signal")
        detail.turn_scores = [ScoreRead(**t) for t in report_doc.get("turn_scores", [])]
    else:
        scores_result = await db.execute(
            select(Score).where(Score.session_id == session_id).order_by(Score.turn_number)
        )
        detail.turn_scores = [
            ScoreRead.model_validate(s) for s in scores_result.scalars().all()
        ]

    return detail


@router.post("/{session_id}/close", response_model=FinalReport)
async def close_session(
    session_id: uuid.UUID,
    terminated: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """terminated=True is the candidate-initiated early stop (Terminate button) —
    same report generation as a natural close, but from whatever turns were scored
    so far, and the session lands in ABANDONED instead of COMPLETED. Not resumable."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your session")
    if session.status != SessionStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Session is not active")

    scores_result = await db.execute(
        select(Score)
        .where(Score.session_id == session_id)
        .order_by(Score.turn_number)
    )
    scores = list(scores_result.scalars().all())

    if not scores:
        if not terminated:
            raise HTTPException(
                status_code=422,
                detail="No scored turns found — interview may still be in progress",
            )
        # Terminated before any answer was scored — finalize with an empty report
        # instead of erroring, so the candidate still gets a clean end state.
        session.status = SessionStatus.ABANDONED
        session.ended_at = datetime.now(timezone.utc)
        await db.commit()
        return FinalReport(
            session_id=session_id,
            total_score=0.0,
            overall_summary="Interview was terminated before any answers were recorded.",
            top_strengths=[],
            key_gaps=[],
            recommendations=[],
            hire_signal="insufficient_data",
            turn_scores=[],
        )

    avg_score = sum(s.score for s in scores) / len(scores)

    transcript_doc = await sessions_col().find_one({"session_id": str(session_id)})
    turns = transcript_doc.get("turns", []) if transcript_doc else []

    closing_prompt = build_closing_prompt(turns, avg_score, session.interview_type.value)
    try:
        llm_svc = await resolve_llm_service(db, session.user_id, session.llm_provider)
        raw = await llm_svc.generate(closing_prompt, system_prompt=CLOSING_SYSTEM, json_mode=True)
        report_data = _extract_json(raw)
    except Exception as exc:
        logger.error("closing_report_failed", session_id=str(session_id), error=str(exc))
        raise HTTPException(status_code=502, detail="Failed to generate closing report")

    session.status = SessionStatus.ABANDONED if terminated else SessionStatus.COMPLETED
    session.ended_at = datetime.now(timezone.utc)
    session.total_score = avg_score
    await db.commit()

    await session_reports_col().insert_one(
        {
            "session_id": str(session_id),
            "user_id": str(session.user_id),
            "interview_type": session.interview_type.value,
            "total_score": round(avg_score, 2),
            "overall_summary": report_data["overall_summary"],
            "top_strengths": report_data["top_strengths"],
            "key_gaps": report_data["key_gaps"],
            "recommendations": report_data["recommendations"],
            "hire_signal": report_data["hire_signal"],
            "turn_scores": [
                {
                    "id": str(s.id),
                    "session_id": str(s.session_id),
                    "turn_number": s.turn_number,
                    "score": s.score,
                    "correctness": s.correctness,
                    "depth": s.depth,
                    "communication": s.communication,
                    "strengths": s.strengths,
                    "weaknesses": s.weaknesses,
                    "improvement": s.improvement,
                    "created_at": s.created_at.isoformat(),
                }
                for s in scores
            ],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    duration_seconds = (session.ended_at - session.started_at).total_seconds()
    logger.info(
        "session_closed_metric",
        session_id=str(session_id),
        total_score=avg_score,
        turn_count=len(scores),
        duration_seconds=round(duration_seconds, 1),
        interview_type=session.interview_type.value,
    )

    return FinalReport(
        session_id=session_id,
        total_score=round(avg_score, 2),
        overall_summary=report_data["overall_summary"],
        top_strengths=report_data["top_strengths"],
        key_gaps=report_data["key_gaps"],
        recommendations=report_data["recommendations"],
        hire_signal=report_data["hire_signal"],
        turn_scores=[ScoreRead.model_validate(s) for s in scores],
    )
