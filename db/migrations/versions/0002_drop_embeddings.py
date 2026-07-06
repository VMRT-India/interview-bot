"""drop embeddings table and vector extension

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-21

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_embeddings_source_id", table_name="embeddings", if_exists=True)
    op.drop_index("ix_embeddings_source_type", table_name="embeddings", if_exists=True)
    op.execute("DROP TABLE IF EXISTS embeddings")
    op.execute("DROP EXTENSION IF EXISTS vector")


def downgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS embeddings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_type VARCHAR(50) NOT NULL,
            source_id UUID NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}'
        )
        """
    )
    op.execute("ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS vector vector(768) NOT NULL")
    op.create_index("ix_embeddings_source_type", "embeddings", ["source_type"])
    op.create_index("ix_embeddings_source_id", "embeddings", ["source_id"])
