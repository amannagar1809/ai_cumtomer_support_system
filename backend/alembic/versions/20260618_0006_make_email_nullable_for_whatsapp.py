"""make email nullable for whatsapp users

Revision ID: 20260618_0006
Revises: 20260615_0005
Create Date: 2026-06-18

Epic 2.2 · User Story 2.2.1 — WhatsApp Business API Integration
- Make email field nullable to support WhatsApp-only users
- Add check constraint to require either email or phone
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260618_0006"
down_revision: Union[str, None] = "20260615_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the existing email format check constraint
    op.drop_constraint("ck_users_email_format", "users", type_="check")

    # Make email column nullable
    op.alter_column("users", "email", nullable=True)

    # Add back the email format check constraint (now allowing NULL)
    op.create_check_constraint(
        "ck_users_email_format",
        "users",
        "email IS NULL OR email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'",
    )

    # Add check constraint to require either email or phone
    op.create_check_constraint(
        "ck_users_email_or_phone_required",
        "users",
        "email IS NOT NULL OR phone IS NOT NULL",
    )


def downgrade() -> None:
    # Drop the new check constraint
    op.drop_constraint("ck_users_email_or_phone_required", "users", type_="check")

    # Drop the email format check constraint
    op.drop_constraint("ck_users_email_format", "users", type_="check")

    # Make email column not nullable again
    op.alter_column("users", "email", nullable=False)

    # Add back the original email format check constraint
    op.create_check_constraint(
        "ck_users_email_format",
        "users",
        "email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'",
    )
