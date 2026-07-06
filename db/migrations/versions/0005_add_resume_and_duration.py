"""add resume_text and target_minutes to sessions (Phase 8 — resume-aware
questions + adaptive, researched interview length)

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("resume_text", sa.Text(), nullable=True))
    op.add_column("sessions", sa.Column("target_minutes", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "target_minutes")
    op.drop_column("sessions", "resume_text")
