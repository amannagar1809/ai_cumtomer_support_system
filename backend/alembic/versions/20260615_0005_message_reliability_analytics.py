"""message reliability, analytics view, and GDPR redaction

Revision ID: 20260615_0005
Revises: 20260602_0004
Create Date: 2026-06-15
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260615_0005"
down_revision: Union[str, None] = "20260602_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE messages
            ADD COLUMN IF NOT EXISTS redacted_at TIMESTAMP,
            ADD COLUMN IF NOT EXISTS redaction_reason VARCHAR(255);
        """
    )
    op.execute(
        """
        ALTER TABLE messages_archive
            ADD COLUMN IF NOT EXISTS redacted_at TIMESTAMP,
            ADD COLUMN IF NOT EXISTS redaction_reason VARCHAR(255);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_messages_redacted_at
            ON messages (redacted_at)
            WHERE redacted_at IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_messages_archive_redacted_at
            ON messages_archive (redacted_at)
            WHERE redacted_at IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION archive_messages_older_than(retention_days INT DEFAULT 90)
        RETURNS BIGINT
        LANGUAGE plpgsql
        AS $$
        DECLARE
            cutoff     TIMESTAMP;
            moved_rows BIGINT;
        BEGIN
            cutoff := CURRENT_TIMESTAMP - (retention_days || ' days')::INTERVAL;

            WITH moved AS (
                DELETE FROM messages
                WHERE "timestamp" < cutoff
                RETURNING
                    id,
                    conversation_id,
                    sender_type,
                    message,
                    language,
                    sentiment,
                    "timestamp",
                    redacted_at,
                    redaction_reason
            ),
            inserted AS (
                INSERT INTO messages_archive (
                    id,
                    conversation_id,
                    sender_type,
                    message,
                    language,
                    sentiment,
                    "timestamp",
                    redacted_at,
                    redaction_reason
                )
                SELECT
                    id,
                    conversation_id,
                    sender_type,
                    message,
                    language,
                    sentiment,
                    "timestamp",
                    redacted_at,
                    redaction_reason
                FROM moved
                RETURNING 1
            )
            SELECT COUNT(*)::BIGINT INTO moved_rows FROM inserted;

            RETURN COALESCE(moved_rows, 0);
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS conversation_message_analytics AS
        SELECT
            c.id AS conversation_id,
            c.user_id,
            c.channel,
            c.status,
            COUNT(m.id)::BIGINT AS message_count,
            COUNT(*) FILTER (WHERE m.sender_type = 'customer')::BIGINT AS customer_message_count,
            COUNT(*) FILTER (WHERE m.sender_type = 'ai')::BIGINT AS ai_message_count,
            COUNT(*) FILTER (WHERE m.sender_type = 'human_agent')::BIGINT AS human_agent_message_count,
            COUNT(*) FILTER (WHERE m.redacted_at IS NOT NULL)::BIGINT AS redacted_message_count,
            MIN(m.timestamp) AS first_message_at,
            MAX(m.timestamp) AS last_message_at
        FROM conversations c
        LEFT JOIN messages m ON m.conversation_id = c.id
        GROUP BY c.id, c.user_id, c.channel, c.status
        WITH NO DATA;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_conversation_message_analytics_conversation_id
            ON conversation_message_analytics (conversation_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS conversation_message_analytics")
    op.execute("DROP INDEX IF EXISTS ix_messages_archive_redacted_at")
    op.execute("DROP INDEX IF EXISTS ix_messages_redacted_at")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION archive_messages_older_than(retention_days INT DEFAULT 90)
        RETURNS BIGINT
        LANGUAGE plpgsql
        AS $$
        DECLARE
            cutoff     TIMESTAMP;
            moved_rows BIGINT;
        BEGIN
            cutoff := CURRENT_TIMESTAMP - (retention_days || ' days')::INTERVAL;

            WITH moved AS (
                DELETE FROM messages
                WHERE "timestamp" < cutoff
                RETURNING id, conversation_id, sender_type, message, language, sentiment, "timestamp"
            ),
            inserted AS (
                INSERT INTO messages_archive (
                    id, conversation_id, sender_type, message, language, sentiment, "timestamp"
                )
                SELECT id, conversation_id, sender_type, message, language, sentiment, "timestamp"
                FROM moved
                RETURNING 1
            )
            SELECT COUNT(*)::BIGINT INTO moved_rows FROM inserted;

            RETURN COALESCE(moved_rows, 0);
        END;
        $$;
        """
    )
    op.execute(
        """
        ALTER TABLE messages_archive
            DROP COLUMN IF EXISTS redaction_reason,
            DROP COLUMN IF EXISTS redacted_at;
        """
    )
    op.execute(
        """
        ALTER TABLE messages
            DROP COLUMN IF EXISTS redaction_reason,
            DROP COLUMN IF EXISTS redacted_at;
        """
    )
