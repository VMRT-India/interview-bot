import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.postgres import get_db
from models.pg.session import Session, SessionStatus
from models.pg.user import User

router = APIRouter(prefix="/stats")
logger = structlog.get_logger()


class PlatformStats(BaseModel):
    total_users: int
    total_sessions: int
    completed_sessions: int
    avg_score: float | None


@router.get("", response_model=PlatformStats)
async def get_platform_stats(db: AsyncSession = Depends(get_db)):
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    total_sessions = (await db.execute(select(func.count()).select_from(Session))).scalar_one()
    completed_sessions = (
        await db.execute(
            select(func.count())
            .select_from(Session)
            .where(Session.status == SessionStatus.COMPLETED)
        )
    ).scalar_one()
    avg_score = (
        await db.execute(
            select(func.avg(Session.total_score)).where(
                Session.status == SessionStatus.COMPLETED
            )
        )
    ).scalar_one()

    return PlatformStats(
        total_users=total_users,
        total_sessions=total_sessions,
        completed_sessions=completed_sessions,
        avg_score=round(avg_score, 2) if avg_score is not None else None,
    )
