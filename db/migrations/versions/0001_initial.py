"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute("CREATE TYPE interviewtype AS ENUM ('TECHNICAL', 'BEHAVIORAL', 'HR')")
    op.execute("CREATE TYPE sessionstatus AS ENUM ('ACTIVE', 'COMPLETED', 'ABANDONED')")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("interview_type", postgresql.ENUM("TECHNICAL", "BEHAVIORAL", "HR", name="interviewtype", create_type=False), nullable=False),
        sa.Column("jd_text", sa.Text, nullable=True),
        sa.Column("status", postgresql.ENUM("ACTIVE", "COMPLETED", "ABANDONED", name="sessionstatus", create_type=False), nullable=False, server_default="ACTIVE"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_score", sa.Float, nullable=True),
    )

    op.create_table(
        "scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_number", sa.Integer, nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("correctness", sa.Float, nullable=False),
        sa.Column("depth", sa.Float, nullable=False),
        sa.Column("communication", sa.Float, nullable=False),
        sa.Column("strengths", sa.Text, nullable=False),
        sa.Column("weaknesses", sa.Text, nullable=False),
        sa.Column("improvement", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vector", sa.Text, nullable=False),  # placeholder — replaced below
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
    )
    op.drop_column("embeddings", "vector")
    op.execute("ALTER TABLE embeddings ADD COLUMN vector vector(768) NOT NULL")

    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_scores_session_id", "scores", ["session_id"])
    op.create_index("ix_embeddings_source_type", "embeddings", ["source_type"])
    op.create_index("ix_embeddings_source_id", "embeddings", ["source_id"])


def downgrade() -> None:
    op.drop_table("embeddings")
    op.drop_table("scores")
    op.drop_table("sessions")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS sessionstatus")
    op.execute("DROP TYPE IF EXISTS interviewtype")
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
