import asyncio
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone

import jwt
import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from config import settings
from db.mongo import sessions_col
from db.postgres import AsyncSessionFactory
from db.redis import get_redis
from models.pg.session import Session, SessionStatus
from models.schemas.jd import JDParsed
from prompts.interviewer import (
    CONCLUDE_CHECK_SYSTEM,
    build_closing_turn_prompt,
    build_conclude_check_prompt,
    build_system_prompt,
    build_user_prompt,
)
from services.auth_service import decode_access_token
from services.company_registry import resolve_company_slug
from services.json_utils import extract_json
from services.llm_service import resolve_llm_service
from services.rag_service import rag_service
from services.scoring_service import score_turn

router = APIRouter()
logger = structlog.get_logger()

_REDIS_TTL = 7200
_HISTORY_WINDOW = 10


def _format_jd_context(parsed: JDParsed) -> str:
    parts = [f"Role: {parsed.role_title}"]
    if parsed.company_name:
        parts.append(f"Company: {parsed.company_name}")
    if parsed.seniority:
        parts.append(f"Seniority: {parsed.seniority}")
    if parsed.required_skills:
        parts.append(f"Required Skills: {', '.join(parsed.required_skills)}")
    if parsed.tech_stack:
        parts.append(f"Tech Stack: {', '.join(parsed.tech_stack)}")
    if parsed.interview_focus:
        parts.append(f"Interview Focus: {', '.join(parsed.interview_focus)}")
    return "\n".join(parts)


async def _load_session(session_id: uuid.UUID) -> Session | None:
    async with AsyncSessionFactory() as db:
        result = await db.execute(select(Session).where(Session.id == session_id))
        return result.scalar_one_or_none()


async def _get_target_minutes(session_id: uuid.UUID) -> int | None:
    """Re-fetched every turn rather than cached from the WS-connect-time session snapshot:
    target_minutes is resolved by a background task (JD parsing / Tavily research) that can
    still be running when the WS connects, especially right after a JD upload. Caching it once
    would silently lock in the pre-resolution default for the whole interview."""
    async with AsyncSessionFactory() as db:
        result = await db.execute(
            select(Session.target_minutes).where(Session.id == session_id)
        )
        return result.scalar_one_or_none()


async def _get_state(session_id: str) -> dict | None:
    raw = await get_redis().get(f"session:{session_id}:state")
    return json.loads(raw) if raw else None


async def _set_state(session_id: str, state: dict) -> None:
    await get_redis().set(
        f"session:{session_id}:state",
        json.dumps(state),
        ex=_REDIS_TTL,
    )


async def _init_state(session_id: str, domain: str) -> dict:
    state = {
        "turn": 0,
        "history": [],
        "difficulty": 2,
        "domain": domain,
        "status": "active",
    }
    await _set_state(session_id, state)
    return state


async def _append_transcript(session_id: str, turn: int, question: str, answer: str) -> None:
    await sessions_col().update_one(
        {"session_id": session_id},
        {
            "$push": {
                "turns": {
                    "turn": turn,
                    "question": question,
                    "answer": answer,
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
            },
            "$setOnInsert": {
                "session_id": session_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        },
        upsert=True,
    )


async def _resolve_jd_context(
    jd_text: str | None,
) -> tuple[str | None, str | None, str | None]:
    """Returns (jd_hash, jd_context_string, company_slug). All None if no JD on session."""
    if not jd_text:
        return None, None, None

    jd_hash = hashlib.sha256(jd_text.encode()).hexdigest()
    try:
        raw_parsed = await get_redis().get(f"jd:{jd_hash}:parsed")
        if raw_parsed:
            parsed = JDParsed.model_validate_json(raw_parsed)
            company_slug = resolve_company_slug(parsed.company_name)
            return jd_hash, _format_jd_context(parsed), company_slug
    except Exception:
        pass

    # Parsed JD not cached yet — fall back to raw text until background task completes
    return jd_hash, jd_text, None


async def _should_close(
    elapsed_min: float,
    target_minutes: int,
    turn: int,
    history: list[dict],
    llm_svc,
    log,
) -> bool:
    """Phase 8 — adaptive, time-aware closing. Under target: always continue (zero extra
    cost). Between target and target*overrun_factor: ask the interviewer LLM whether it has
    gathered enough signal. Past the overrun ceiling: force-close regardless (safety valve).
    `settings.max_interview_turns` is a separate, generous absolute circuit breaker."""
    if turn >= settings.max_interview_turns:
        return True
    if elapsed_min < target_minutes:
        return False
    if elapsed_min >= target_minutes * settings.interview_overrun_factor:
        return True
    if not history:
        return False
    try:
        raw = await llm_svc.generate(
            build_conclude_check_prompt(history),
            system_prompt=CONCLUDE_CHECK_SYSTEM,
            json_mode=True,
        )
        return bool(extract_json(raw).get("conclude", False))
    except Exception as exc:
        log.warning("conclude_check_failed", error=str(exc))
        return False


@router.websocket("/ws/interview/{session_id}")
async def interview_ws(websocket: WebSocket, session_id: uuid.UUID, token: str | None = None):
    await websocket.accept()
    log = logger.bind(session_id=str(session_id))

    if not token:
        await websocket.send_json({"type": "error", "content": "Missing auth token"})
        await websocket.close(code=1008)
        return
    try:
        user_id = decode_access_token(token)
    except jwt.PyJWTError:
        await websocket.send_json({"type": "error", "content": "Invalid or expired auth token"})
        await websocket.close(code=1008)
        return

    session = await _load_session(session_id)
    if not session or session.status != SessionStatus.ACTIVE:
        await websocket.send_json({"type": "error", "content": "Session not found or not active"})
        await websocket.close(code=1008)
        return
    if session.user_id != user_id:
        await websocket.send_json({"type": "error", "content": "Not your session"})
        await websocket.close(code=1008)
        return

    domain = session.interview_type.value
    jd_hash, jd_context, company_slug = await _resolve_jd_context(session.jd_text)
    state = await _get_state(str(session_id)) or await _init_state(str(session_id), domain)

    async with AsyncSessionFactory() as db:
        llm_svc = await resolve_llm_service(db, session.user_id, session.llm_provider)

    try:
        while True:
            turn_start = time.monotonic()
            turn = state["turn"]
            history = state["history"][-_HISTORY_WINDOW:]
            elapsed_min = (
                datetime.now(timezone.utc) - session.started_at
            ).total_seconds() / 60
            target_minutes = (
                await _get_target_minutes(session_id) or settings.default_interview_target_minutes
            )

            should_close = await _should_close(
                elapsed_min, target_minutes, turn, history, llm_svc, log
            )
            if should_close:
                state["status"] = "closing"
                await _set_state(str(session_id), state)

                closing_system, closing_user = build_closing_turn_prompt(domain, history)
                tokens: list[str] = []
                async for token in llm_svc.stream_generate(
                    closing_user, system_prompt=closing_system
                ):
                    tokens.append(token)
                    await websocket.send_json({"type": "token", "content": token})
                closing_message = "".join(tokens).strip()
                await websocket.send_json({"type": "question_end"})

                asyncio.create_task(
                    _append_transcript(str(session_id), turn + 1, closing_message, "")
                )
                log.info("interview_closing", turn=turn, elapsed_min=round(elapsed_min, 1))

                await websocket.send_json({"type": "session_end", "content": "Session ended."})
                break

            rag_query = history[-1]["answer"] if history else domain
            context = await rag_service.retrieve(
                rag_query, domain, top_k=3, jd_hash=jd_hash, company_slug=company_slug
            )

            system_prompt = build_system_prompt(
                domain, state["difficulty"], jd_context, context, session.resume_text
            )

            user_prompt = build_user_prompt(history, turn)
            tokens: list[str] = []
            async for token in llm_svc.stream_generate(user_prompt, system_prompt=system_prompt):
                tokens.append(token)
                await websocket.send_json({"type": "token", "content": token})

            question = "".join(tokens).strip()
            await websocket.send_json({"type": "question_end"})

            raw_msg = await websocket.receive_text()
            try:
                answer = json.loads(raw_msg).get("content", raw_msg)
            except (json.JSONDecodeError, AttributeError):
                answer = raw_msg

            state["turn"] += 1
            state["history"].append({"question": question, "answer": answer})
            await _set_state(str(session_id), state)

            asyncio.create_task(
                _append_transcript(str(session_id), state["turn"], question, answer)
            )
            asyncio.create_task(
                score_turn(session_id, state["turn"], question, answer, llm_svc=llm_svc)
            )

            log.info(
                "turn_complete",
                turn=state["turn"],
                turn_latency_ms=round((time.monotonic() - turn_start) * 1000),
                rag_chunk_count=len(context),
            )

    except WebSocketDisconnect:
        log.info("client_disconnected")
    except Exception as exc:
        log.error("ws_error", error=str(exc))
        try:
            await websocket.send_json({"type": "error", "content": "Internal server error"})
        except Exception:
            pass
