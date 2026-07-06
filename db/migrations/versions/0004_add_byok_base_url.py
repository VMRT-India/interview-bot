"""add base_url to user_api_keys (arbitrary OpenAI-compatible BYOK providers)
and llm_provider to sessions (per-session model selection)

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_api_keys", sa.Column("base_url", sa.String(500), nullable=True))
    op.add_column("sessions", sa.Column("llm_provider", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "llm_provider")
    op.drop_column("user_api_keys", "base_url")
