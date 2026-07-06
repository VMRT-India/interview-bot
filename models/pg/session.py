import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Float, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from db.postgres import Base


class InterviewType(enum.Enum):
    TECHNICAL = "TECHNICAL"
    BEHAVIORAL = "BEHAVIORAL"
    HR = "HR"


class SessionStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    interview_type: Mapped[InterviewType] = mapped_column(
        Enum(InterviewType, name="interviewtype"), nullable=False
    )
    jd_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # resolved once: JD-stated -> Tavily-researched -> default_interview_target_minutes
    llm_provider: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # None = app default (e.g. alpha-tester); else BYOK provider chosen at creation
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="sessionstatus"),
        nullable=False,
        server_default=SessionStatus.ACTIVE.value,
    )
    started_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="sessions")  # noqa: F821
    scores: Mapped[list["Score"]] = relationship(  # noqa: F821
        "Score", back_populates="session", lazy="selectin"
    )

    @property
    def has_resume(self) -> bool:
        return self.resume_text is not None
