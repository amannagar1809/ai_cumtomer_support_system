"""create messages table (partitioned) + archive policy

Revision ID: 20260602_0003
Revises: 20260602_0002
Create Date: 2026-06-02

Epic 1.2 · User Story 1.2.1 — Messages table
"""

from pathlib import Path
from typing import Sequence, Union

from alembic import op

revision: str = "20260602_0003"
down_revision: Union[str, None] = "20260602_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = Path(__file__).resolve().parents[2] / "db" / "schema" / "003_messages.sql"


def upgrade() -> None:
    op.execute(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS archive_messages_older_than(INT)")
    op.execute("DROP FUNCTION IF EXISTS ensure_messages_partitions(INT)")
    op.execute("DROP FUNCTION IF EXISTS create_messages_partition(INT, INT)")
    op.execute("DROP TABLE IF EXISTS messages_archive CASCADE")
    op.execute("DROP TABLE IF EXISTS messages CASCADE")
    op.execute("DROP TYPE IF EXISTS message_sender_type")
