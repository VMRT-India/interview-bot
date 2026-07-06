import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    turn_number: int
    score: float
    correctness: float
    depth: float
    communication: float
    strengths: str
    weaknesses: str
    improvement: str
    created_at: datetime


class TurnScoreResult(BaseModel):
    correctness: float
    depth: float
    communication: float
    score: float
    strengths: str
    weaknesses: str
    improvement: str
