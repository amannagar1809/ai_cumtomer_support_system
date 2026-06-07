"""create users table

Revision ID: 20260602_0001
Revises:
Create Date: 2026-06-02

Epic 1.2 · User Story 1.2.1 — Users table only
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260602_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

customer_type_enum = postgresql.ENUM(
    "regular",
    "premium",
    "vip",
    name="customer_type",
    create_type=False,
)


def upgrade() -> None:
    customer_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("language", sa.String(length=10), server_default="en", nullable=False),
        sa.Column(
            "customer_type",
            customer_type_enum,
            server_default="regular",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint(
            "email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'",
            name="ck_users_email_format",
        ),
        sa.CheckConstraint(
            "phone IS NULL OR phone ~ '^\\+[1-9][0-9]{1,14}$'",
            name="ck_users_phone_e164",
        ),
    )

    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_index("ix_users_phone", "users", ["phone"], unique=False)
    op.create_index("ix_users_customer_type", "users", ["customer_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_customer_type", table_name="users")
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    customer_type_enum.drop(op.get_bind(), checkfirst=True)
