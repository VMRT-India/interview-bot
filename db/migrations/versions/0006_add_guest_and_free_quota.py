"""add users.is_guest and users.free_sessions_used (guest trial + free-tier quota)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_guest", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column("free_sessions_used", sa.Integer(), nullable=False, server_default="0"),
    )

    op.drop_constraint("ck_users_email_or_phone", "users", type_="check")
    op.create_check_constraint(
        "ck_users_email_or_phone",
        "users",
        "is_guest OR email IS NOT NULL OR phone_number IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_email_or_phone", "users", type_="check")
    op.create_check_constraint(
        "ck_users_email_or_phone",
        "users",
        "email IS NOT NULL OR phone_number IS NOT NULL",
    )
    op.drop_column("users", "free_sessions_used")
    op.drop_column("users", "is_guest")
