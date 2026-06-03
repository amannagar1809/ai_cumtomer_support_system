-- Epic 1.2 · User Story 1.2.1 — Messages table (partitioned)
-- Requires: 002_conversations.sql

CREATE TYPE message_sender_type AS ENUM ('customer', 'ai', 'human_agent');

-- ---------------------------------------------------------------------------
-- Hot storage: partitioned by month on "timestamp"
-- PK includes partition key (PostgreSQL requirement)
-- ---------------------------------------------------------------------------
CREATE TABLE messages (
    id              UUID                NOT NULL DEFAULT gen_random_uuid(),
    conversation_id UUID                NOT NULL,
    sender_type     message_sender_type NOT NULL,
    message         TEXT                NOT NULL,
    language        VARCHAR(10)         NOT NULL DEFAULT 'en',
    sentiment       JSONB,
    "timestamp"     TIMESTAMP           NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id, "timestamp"),
    CONSTRAINT fk_messages_conversation_id_conversations
        FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
) PARTITION BY RANGE ("timestamp");

-- Full-text search (propagates to all partitions)
CREATE INDEX ix_messages_message_fts
    ON messages USING GIN (to_tsvector('english', message));

-- Conversation thread lookup
CREATE INDEX ix_messages_conversation_id_timestamp
    ON messages (conversation_id, "timestamp" DESC);

-- ---------------------------------------------------------------------------
-- Cold storage: rows older than 90 days (see archive_messages_older_than)
-- ---------------------------------------------------------------------------
CREATE TABLE messages_archive (
    id              UUID                NOT NULL,
    conversation_id UUID                NOT NULL,
    sender_type     message_sender_type NOT NULL,
    message         TEXT                NOT NULL,
    language        VARCHAR(10)         NOT NULL,
    sentiment       JSONB,
    "timestamp"     TIMESTAMP           NOT NULL,
    archived_at     TIMESTAMP           NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id, "timestamp")
);

CREATE INDEX ix_messages_archive_timestamp ON messages_archive ("timestamp");
CREATE INDEX ix_messages_archive_conversation_id ON messages_archive (conversation_id);
CREATE INDEX ix_messages_archive_message_fts
    ON messages_archive USING GIN (to_tsvector('english', message));

COMMENT ON TABLE messages IS 'Hot message store; RANGE partitioned by month on timestamp';
COMMENT ON TABLE messages_archive IS 'Cold store for messages archived after 90-day retention';
COMMENT ON COLUMN messages.sentiment IS 'JSON e.g. {"score": 0.82, "label": "positive"}';

-- ---------------------------------------------------------------------------
-- Partition management
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION create_messages_partition(p_year INT, p_month INT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    partition_name TEXT;
    range_start    TIMESTAMP;
    range_end      TIMESTAMP;
BEGIN
    partition_name := format('messages_y%sm%s', p_year, lpad(p_month::TEXT, 2, '0'));
    range_start := make_timestamp(p_year, p_month, 1, 0, 0, 0);
    range_end := range_start + INTERVAL '1 month';

    IF NOT EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = partition_name AND n.nspname = 'public'
    ) THEN
        EXECUTE format(
            'CREATE TABLE %I PARTITION OF messages FOR VALUES FROM (%L) TO (%L)',
            partition_name,
            range_start,
            range_end
        );
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION ensure_messages_partitions(months_ahead INT DEFAULT 3)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    i INT;
    target DATE;
BEGIN
    FOR i IN 0..months_ahead LOOP
        target := (date_trunc('month', CURRENT_DATE) + (i || ' months')::INTERVAL)::DATE;
        PERFORM create_messages_partition(
            EXTRACT(YEAR FROM target)::INT,
            EXTRACT(MONTH FROM target)::INT
        );
    END LOOP;
END;
$$;

-- ---------------------------------------------------------------------------
-- Archiving policy: move messages older than retention_days (default 90)
-- Schedule daily via pg_cron or application cron:
--   SELECT archive_messages_older_than(90);
-- ---------------------------------------------------------------------------
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

-- Bootstrap partitions: current month + 12 months ahead
SELECT ensure_messages_partitions(12);
