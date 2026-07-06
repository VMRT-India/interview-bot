import uuid

from sqlalchemy import CheckConstraint, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from db.postgres import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "is_guest OR email IS NOT NULL OR phone_number IS NOT NULL",
            name="ck_users_email_or_phone",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_alpha_tester: Mapped[bool] = mapped_column(server_default=text("false"), nullable=False)
    is_guest: Mapped[bool] = mapped_column(server_default=text("false"), nullable=False)
    free_sessions_used: Mapped[int] = mapped_column(server_default=text("0"), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sessions: Mapped[list["Session"]] = relationship(  # noqa: F821
        "Session", back_populates="user", lazy="selectin"
    )
    oauth_identities: Mapped[list["OAuthIdentity"]] = relationship(  # noqa: F821
        "OAuthIdentity", back_populates="user", lazy="selectin"
    )
    api_keys: Mapped[list["UserAPIKey"]] = relationship(  # noqa: F821
        "UserAPIKey", back_populates="user", lazy="selectin"
    )

    @property
    def has_password(self) -> bool:
        return self.password_hash is not None
