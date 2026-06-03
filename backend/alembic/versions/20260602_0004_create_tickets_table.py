"""create tickets table + status transition rules

Revision ID: 20260602_0004
Revises: 20260602_0003
Create Date: 2026-06-02

Epic 1.2 · User Story 1.2.1 — Tickets table
"""

from pathlib import Path
from typing import Sequence, Union

from alembic import op

revision: str = "20260602_0004"
down_revision: Union[str, None] = "20260602_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = Path(__file__).resolve().parents[2] / "db" / "schema" / "004_tickets.sql"


def upgrade() -> None:
    op.execute(_SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_tickets_status_rules ON tickets")
    op.execute("DROP FUNCTION IF EXISTS enforce_ticket_status_rules()")
    op.execute("DROP TABLE IF EXISTS tickets CASCADE")
    op.execute("DROP TYPE IF EXISTS ticket_status")
    op.execute("DROP TYPE IF EXISTS ticket_priority")
