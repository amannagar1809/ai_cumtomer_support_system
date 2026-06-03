"""create conversations table

Revision ID: 20260602_0002
Revises: 20260602_0001
Create Date: 2026-06-02

Epic 1.2 · User Story 1.2.1 — Conversations table
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260602_0002"
down_revision: Union[str, None] = "20260602_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

conversation_channel_enum = postgresql.ENUM(
    "web",
    "whatsapp",
    "email",
    "telegram",
    "mobile",
    name="conversation_channel",
    create_type=True,
)

conversation_status_enum = postgresql.ENUM(
    "active",
    "resolved",
    "escalated",
    "closed",
    name="conversation_status",
    create_type=True,
)


def upgrade() -> None:
    conversation_channel_enum.create(op.get_bind(), checkfirst=True)
    conversation_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "conversations",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("channel", conversation_channel_enum, nullable=False),
        sa.Column(
            "status",
            conversation_status_enum,
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_conversations_user_id_users",
            ondelete="CASCADE",
        ),
    )

    op.create_index(
        "ix_conversations_user_id_status",
        "conversations",
        ["user_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_user_id_status", table_name="conversations")
    op.drop_table("conversations")
    conversation_status_enum.drop(op.get_bind(), checkfirst=True)
    conversation_channel_enum.drop(op.get_bind(), checkfirst=True)
