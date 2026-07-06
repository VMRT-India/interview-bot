import time
import uuid

import structlog

from db.postgres import AsyncSessionFactory
from models.pg.score import Score
from models.schemas.score import TurnScoreResult
from prompts.evaluator import SYSTEM_PROMPT, build_eval_prompt
from services.json_utils import extract_json as _extract_json
from services.llm_service import llm_service

logger = structlog.get_logger()


async def score_turn(
    session_id: uuid.UUID,
    turn_number: int,
    question: str,
    answer: str,
    llm_svc=None,
) -> TurnScoreResult | None:
    llm_svc = llm_svc or llm_service
    prompt = build_eval_prompt(question, answer)
    start = time.monotonic()
    try:
        raw = await llm_svc.generate(prompt, system_prompt=SYSTEM_PROMPT, json_mode=True)
        data = _extract_json(raw)
        result = TurnScoreResult(**data)
    except Exception as exc:
        logger.warning(
            "score_turn_failed",
            session_id=str(session_id),
            turn=turn_number,
            error=str(exc),
        )
        return None

    logger.info(
        "score_turn_metric",
        session_id=str(session_id),
        turn=turn_number,
        score=result.score,
        correctness=result.correctness,
        depth=result.depth,
        communication=result.communication,
        latency_ms=round((time.monotonic() - start) * 1000),
    )

    try:
        async with AsyncSessionFactory() as db:
            score = Score(
                session_id=session_id,
                turn_number=turn_number,
                score=result.score,
                correctness=result.correctness,
                depth=result.depth,
                communication=result.communication,
                strengths=result.strengths,
                weaknesses=result.weaknesses,
                improvement=result.improvement,
            )
            db.add(score)
            await db.commit()
    except Exception as exc:
        logger.error(
            "score_write_failed",
            session_id=str(session_id),
            turn=turn_number,
            error=str(exc),
        )

    return result
