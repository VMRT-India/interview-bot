import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from models.pg.session import InterviewType, SessionStatus
from models.schemas.score import ScoreRead


class SessionCreate(BaseModel):
    interview_type: InterviewType
    jd_text: str | None = None
    llm_provider: str | None = None  # BYOK provider to use; None = app default


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    interview_type: InterviewType
    status: SessionStatus
    started_at: datetime
    ended_at: datetime | None
    total_score: float | None
    llm_provider: str | None
    target_minutes: int | None
    has_resume: bool = False


class SessionDetail(SessionRead):
    """SessionRead plus the persisted closing report (if the session has been closed
    and its report was written to MongoDB `session_reports`). Narrative fields are
    None for sessions that are still ACTIVE or predate this feature; turn_scores is
    always populated from Postgres `scores` when available."""

    overall_summary: str | None = None
    top_strengths: list[str] = []
    key_gaps: list[str] = []
    recommendations: list[str] = []
    hire_signal: str | None = None
    turn_scores: list[ScoreRead] = []


class FinalReport(BaseModel):
    session_id: uuid.UUID
    total_score: float
    overall_summary: str
    top_strengths: list[str]
    key_gaps: list[str]
    recommendations: list[str]
    hire_signal: str
    turn_scores: list[ScoreRead]
